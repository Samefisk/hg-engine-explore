"""Exact legacy rows derived from independent replay of retained memory data."""
from copy import deepcopy
from tools.overworld.devtools_wild_battle_handoff_measurement import KIND, REQUIREMENT, replay, require

CLAIMS = ("natural-input", "live-actor-identity", "battle-capture-handoff")
FAULTS = ("battle-missing-request", "battle-wrong-personality", "battle-stale-generation",
          "battle-wrong-slot", "battle-missing-a", "battle-missing-motion", "battle-native-gap")


def contract():
    def row(name, value, typ):
        return dict(name=name, expected=value, operator="eq", type=typ, validator="meaningful-observation")
    return {
        "natural-input": [row("wild-battle-a-input-milestones", [1,1,1,1], "array")],
        "live-actor-identity": [row("wild-battle-role", "WILD", "string"),
            row("wild-battle-identity-flags", [1,"WILD",19,1,1,1,1,1,1], "array")],
        "battle-capture-handoff": [row("wild-battle-request-count", 1, "integer"),
            row("wild-battle-pending-species", 19, "integer"),
            *[dict(name="wild-battle-"+name+"-match", operator="eq", type="array",
                   validator="positive-identical-values", minItems=2)
              for name in ("slot", "personality", "encounter-generation")]],
    }


def measurements(result, record):
    result = result.get("measurements", {}).get(KIND, result)
    require(result.get("closed") is True and result.get("passed") is True
            and result.get("acceptedProof") is False, "battle requires closed measurement")
    checked = replay(result)
    require(checked["passed"] is True, "battle independent replay failed: " + "; ".join(checked["failures"]))
    require(record.get("sessionCleanup") == dict(sessionId=record.get("sessionId"), closed=True, errors=[]),
            "battle private session did not close cleanly")
    request, subject = checked["request"], checked["subject"]
    values = [[1,1,1,1], "WILD", [1,"WILD",19,1,1,1,1,1,1], 1, request["pending"]["species"],
              [subject["handle"]["slot"]+1, request["pending"]["slot"]+1],
              [subject["subjectIdentity"], request["pending"]["personality"]],
              [subject["handle"]["encounterGeneration"], request["pending"]["encounterGeneration"]]]
    rows = []
    for claim, rules in contract().items():
        for rule in rules:
            rows.append(dict(rule, claim=claim, value=values.pop(0), passed=True))
    return rows


def negative(result, fault):
    require(fault in FAULTS, "unknown battle fault")
    copied = deepcopy(result)
    for snapshot, events in copied["journal"]:
        if fault == "battle-missing-a":
            snapshot["selector"]["newKeys"] &= ~1
            snapshot["selector"]["rawNew"] &= ~1
        for event in events:
            data = event.get("data", {})
            if fault == "battle-missing-motion" and data.get("event") == "CONTROL_RETURNED":
                data["event"] = "WORLD_EFFECT"
            if data.get("observation") != "wild-battle-request": continue
            if fault == "battle-missing-request": data["observation"] = "other"
            elif fault == "battle-wrong-personality": data["pending"]["personality"] += 1
            elif fault == "battle-stale-generation": data["pending"]["encounterGeneration"] += 1
            elif fault == "battle-wrong-slot": data["pending"]["slot"] += 1
            elif fault == "battle-native-gap": data["sequence"] += 1
    return copied


def validate_negative_result(result, fault):
    require(fault in FAULTS, "unknown battle fault")
    if "rejected" in result:
        require(result == {"fault": fault, "mutated": True, "rejected": True,
                           "acceptedProof": False},
                "battle negative control result differs")
        return True
    reason = {"battle-missing-request": "missing native wild-battle-request receipt",
              "battle-missing-a": "battle request precedes natural A input or motion",
              "battle-missing-motion": "battle A input is not a prepared approach",
              "battle-native-gap": "battle native sequence gap"}.get(fault, "battle pending identity differs")
    reasons = set()
    def collect(value):
        if isinstance(value, str):
            reasons.add(value)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            for key in ("message", "detail", "details", "failures"):
                collect(value.get(key))
    collect(result.get("failures", []))
    require(result.get("passed") is False and reason in reasons,
            "battle negative did not reject the named fault")
    return True


class WildBattleHandoffNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown battle fault")
        self.fault, self.mutated = fault, False

    @property
    def applied(self):
        return self.mutated

    def mutate(self, row, subjects):
        if self.mutated:
            return row
        changed = deepcopy(row)
        handles = {subject["handle"]["value"] for subject in subjects.values()}
        if self.fault == "battle-missing-a":
            for snapshot in changed.get("samples", []):
                if snapshot.get("selector", {}).get("newKeys", 0) & 1:
                    snapshot["selector"]["newKeys"] &= ~1
                    snapshot["selector"]["rawNew"] &= ~1
                    self.mutated = True
                    return changed
        for event in changed.get("events", []):
            data = event.get("data", {})
            if self.fault == "battle-missing-motion" and data.get("actorHandle") in handles \
                    and data.get("event") == "CONTROL_RETURNED":
                data["event"] = "WORLD_EFFECT"
                self.mutated = True
                return changed
            if data.get("observation") != "wild-battle-request" \
                    or data.get("subject", {}).get("handle", {}).get("value") not in handles:
                continue
            if self.fault == "battle-missing-request": data["observation"] = "other"
            elif self.fault == "battle-wrong-personality": data["pending"]["personality"] += 1
            elif self.fault == "battle-stale-generation": data["pending"]["encounterGeneration"] += 1
            elif self.fault == "battle-wrong-slot": data["pending"]["slot"] += 1
            elif self.fault == "battle-native-gap": data["sequence"] += 1
            else: continue
            self.mutated = True
            return changed
        return row

    def result(self, replay_result):
        require(self.mutated, "negative control never reached selected live subject")
        return {"fault": self.fault, "mutated": True,
                "rejected": replay_result.get("passed") is False
                            and bool(replay_result.get("failures")),
                "acceptedProof": False}
