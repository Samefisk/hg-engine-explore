"""Exact running-hit claims and copied faults; no alternate recorder."""
from copy import deepcopy
from tools.overworld.devtools_player_health_running_hit_measurement import (
    KIND, REQUIREMENT, MIN_FRAMES, NEUTRAL_FRAMES, require,
)

CLAIMS = ("live-actor-identity", "profile-resolution", "engine-boundary", "natural-input", "control-release")
NAMES = {
    "live-actor-identity": ("one-current-wild-weepinbell",),
    "profile-resolution": ("current-ambush-jump1-contact",),
    "engine-boundary": ("real-running-hit-minus20", "same-frame-idle-animation-at-knockback-terminal"),
    "natural-input": ("native-up-b-run-admission-before-hit",),
    "control-release": ("sixteen-neutral-idle-frames-after-terminal",),
}
FAULTS = ("missing-run-admission", "missing-running-animation", "stale-weepinbell", "wrong-profile",
          "wrong-damage", "stale-terminal-animation", "stale-terminal-renderer", "missing-neutral-frame")


def contract():
    return {claim: [dict(name=n, operator="eq", type="integer", validator="meaningful-observation", expected=1)
                    for n in names] for claim, names in NAMES.items()}


def measurements(replay, record):
    result = replay.get("measurements", {}).get(KIND, {})
    frames = [result.get(n) for n in ("runAdmissionFrame", "runningFrame", "crossingFrame", "terminalFrame")]
    require(replay.get("passed") is True and result.get("ready") is True
            and all(type(f) is int for f in frames) and frames[0] <= frames[1] < frames[2] < frames[3]
            and result.get("neutralFrames") == NEUTRAL_FRAMES and result.get("hpAfter") == 80
            and result.get("observedFrames") == replay.get("observedFrames")
            and result.get("observedFrames", 0) >= MIN_FRAMES
            and result.get("observedFrameUnit") == "completed-game-frame"
            and isinstance(result.get("subject"), dict) and isinstance(result.get("terminalTile"), list),
            "running-hit replay lacks exact admission/contact/idle terminal")
    require(record.get("sessionCleanup") == dict(sessionId=record.get("sessionId"), closed=True, errors=[]),
            "running-hit lacks owned cleanup")
    return [dict(claim=c, name=n, value=1, operator="eq", expected=1, passed=True)
            for c, names in NAMES.items() for n in names]


class RunningHitNegative:
    def __init__(self, fault):
        require(fault in FAULTS, "unknown running-hit copied control")
        self.fault, self.applied = fault, False

    def mutate(self, row, subjects):
        changed = deepcopy(row)
        action = row.get("action")
        if action == "run-to-contact":
            if self.fault == "missing-run-admission":
                changed["events"] = [e for e in changed.get("events", [])
                                     if e.get("data", {}).get("observation") != "player-step-admitted"]
            for sample in changed.get("samples", []):
                player = sample["player"]
                if self.fault == "missing-running-animation" and player.get("movement_cmd") == 88:
                    player["movement_animation"] = 0
                if self.fault == "stale-weepinbell":
                    actor = next(a for a in sample["actors"] if a["handle"] == subjects["weepinbell"]["handle"])
                    actor["subjectIdentity"] += 1
            if self.fault == "wrong-profile" and changed.get("profileCache"):
                for p in changed["profileCache"]["resolvedProfiles"]:
                    raw = bytearray.fromhex(p["resultHex"])
                    raw[72] = 0
                    p["resultHex"] = raw.hex()
        if action == "finish-knockback":
            for sample in changed.get("samples", []):
                player = sample["player"]
                if player.get("movement_cmd") == 255:
                    if self.fault == "stale-terminal-animation": player["movement_animation"] = 2
                    if self.fault == "stale-terminal-renderer": player["movement_render_words"][0] |= 2 << 16
        if action == "after-knockback" and self.fault == "wrong-damage":
            changed["receipt"]["playerHealth"].update(hp=85, savedHp=85)
        if action == "neutral-after-knockback" and self.fault == "missing-neutral-frame" and not self.applied:
            # Remove actual copied evidence while retaining declared counts.
            changed["samples"].pop(0)
            self.applied = True
        self.applied |= changed != row
        return changed


def validate_negative_result(result, fault):
    require(fault in FAULTS and result.get("passed") is False and result.get("failures"),
            "running-hit copied control did not reject")
    expected = {
        "missing-run-admission": "real Run admission", "missing-running-animation": "earlier real Run",
        "stale-weepinbell": "different subject or role", "wrong-profile": "attacking 1/16/20 and Jump1",
        "wrong-damage": "HP, damage, or hit count differs", "stale-terminal-animation": "terminal animation",
        "stale-terminal-renderer": "terminal animation", "missing-neutral-frame": "raw chunk has missing",
    }[fault]
    require(expected in str(result.get("measurements", {}).get(KIND, {}).get("failures", result.get("failures"))),
            "running-hit copied control rejected at another guard: " + fault)
