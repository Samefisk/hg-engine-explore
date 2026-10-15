"""One mounted skid-hit witness and its copied-data controls."""
from copy import deepcopy

from tools.overworld.devtools_pokemon_skid_hit_measurement import KIND, REQUIREMENT, MIN_FRAMES

NAMES = {
    "live-actor-identity": ("current-stantler-and-ambush-generation",),
    "profile-resolution": ("ordinary-ambush-attacking-jump1-profile",),
    "engine-boundary": ("one-real-party-and-rider-20hp-hit-during-skid", "one-immediate-crash-without-old-skid-commit"),
    "rendered-motion": ("crash-ground-then-shared-jump1-arc-and-landing",),
    "natural-input": ("up8-right24-natural-ambush-collision",),
    "control-release": ("crash-hold-and-ten-restored-mounted-frames",),
}
CLAIMS = tuple(NAMES)
FAULTS = ("skid-hit-missing-hp", "skid-hit-stale-target", "skid-hit-no-crash",
          "skid-hit-old-commit", "skid-hit-no-ground", "skid-hit-early-jump",
          "skid-hit-no-control", "skid-hit-seat-height")
FAILURES = {
    "skid-hit-missing-hp": "combat HP has no current native record",
    "skid-hit-stale-target": "combat HP target is missing or stale",
    "skid-hit-no-crash": "exactly one immediate Crash",
    "skid-hit-old-commit": "SKID committed, finished or canceled",
    "skid-hit-no-ground": "restore the current logical ground",
    "skid-hit-early-jump": "before completion",
    "skid-hit-no-control": "land one tile and release its control",
    "skid-hit-seat-height": "land one tile and release its control",
}


def contract():
    return {claim: [dict(name=name, operator="eq", type="integer",
                        validator="meaningful-observation", expected=1) for name in names]
            for claim, names in NAMES.items()}


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    crash = meter.get("crash") or {}
    jump = meter.get("forcedKnockbacks", {}).get("stantler", {})
    if (replay.get("passed") is not True or replay.get("failures") != []
            or meter.get("ready") is not True or meter.get("passed") is not True
            or meter.get("acceptedProof") is not False
            or meter.get("observedFrames") != MIN_FRAMES
            or replay.get("observedFrames") != MIN_FRAMES
            or set(meter.get("subjects", {})) != {"stantler", "weepinbell"}
            or meter.get("attackFrames", 0) < 1 or meter.get("cleanFrames", 0) < 10
            or meter.get("jumpArcs") != {"stantler": True} or meter.get("landed") != {"stantler": True}
            or len(meter.get("hits", {}).get("stantler", [])) != 1
            or len(meter.get("crashEffects", [])) != 1
            or crash.get("finished") is not True or "groundFrame" not in crash
            or not crash["hitFrame"] <= crash["groundFrame"] < crash.get("finishFrame", 0)
            or jump.get("finished") is not True or jump.get("startFrame") != crash.get("finishFrame", -2)+1
            or any(jump.get("plan", {}).get(key) != value for key, value in
                   (("kind", 2), ("duration", 13), ("distance", 1), ("arcHeightQ4", 16), ("flags", 1)))):
        raise ValueError("skid hit lacks immediate Crash, old-motion settlement and the same restored Jump")
    if record.get("sessionCleanup") != dict(sessionId=record.get("sessionId"), closed=True, errors=[]):
        raise ValueError("skid-hit private session did not close")
    return [dict(claim=claim, name=name, value=1, operator="eq", expected=1, passed=True)
            for claim, names in NAMES.items() for name in names]


class PokemonSkidHitNegative:
    def __init__(self, fault):
        if fault not in FAULTS: raise ValueError("unknown skid-hit copied-data control")
        self.fault, self.applied = fault, False

    def mutate(self, row, subjects):
        changed = deepcopy(row)
        if row.get("phase") != "observe": return row
        samples = list(changed.get("samples", []))
        if isinstance(changed.get("snapshot"), dict): samples.append(changed["snapshot"])
        for sample in samples:
            target = next((t for t in sample.get("pokemonCombat", {}).get("targets", [])
                           if t.get("species") == 234), None)
            if self.fault == "skid-hit-missing-hp" and changed.get("samples"):
                sample.pop("pokemonCombat", None); self.applied = True
            elif self.fault == "skid-hit-stale-target" and target and changed.get("samples"):
                target["handle"]["encounterGeneration"] += 1; self.applied = True
            elif self.fault == "skid-hit-no-ground" and target and target.get("crashPhase") == "PLAYING":
                sample["player"]["unk88_y"] += 4096; self.applied = True
            elif self.fault == "skid-hit-seat-height" and target and target.get("motion", {}).get("plan", {}).get("flags") == 1:
                sample["player"]["face_y"] += 4096; self.applied = True
        handle = subjects.get("stantler", {}).get("handle", {}).get("value")
        events = changed.get("events", [])
        if self.fault in ("skid-hit-no-crash", "skid-hit-no-control"):
            name = "WORLD_EFFECT" if self.fault == "skid-hit-no-crash" else "CONTROL_RETURNED"
            kept = [e for e in events if not (e.get("kind") == "native"
                    and e.get("data", {}).get("actorHandle") == handle
                    and e["data"].get("event") == name
                    and (name != "WORLD_EFFECT" or e["data"].get("valueA") == 3))]
            if len(kept) != len(events): changed["events"] = kept; self.applied = True
        elif self.fault in ("skid-hit-old-commit", "skid-hit-early-jump"):
            crash = next((e for e in events if e.get("data", {}).get("actorHandle") == handle
                          and e["data"].get("event") == "WORLD_EFFECT" and e["data"].get("valueA") == 3), None)
            if crash:
                fake = deepcopy(crash); fake["data"].update(sequence=fake["data"]["sequence"]+1)
                if self.fault == "skid-hit-old-commit": fake["data"].update(event="LOGICAL_COMMIT", valueA=6, valueB=4)
                else: fake["data"].update(event="MOTION_STARTED", valueA=2, valueB=13)
                changed["events"].append(fake); self.applied = True
        return changed


def validate_negative_result(result, fault):
    if fault not in FAULTS or result.get("passed") is not False or not result.get("failures") \
            or FAILURES[fault] not in str(result["failures"]):
        raise ValueError("skid-hit control did not reject its named fault: " + fault)
    return True
