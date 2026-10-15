"""Exact acceptance rows for the bounded Stantler follower stop witness."""
from copy import deepcopy

from tools.overworld.devtools_follower_stop_measurement import KIND, REQUIREMENT, IDLE_FRAMES
from tools.overworld.devtools_profile_feature_proof import _spec, need

CLAIMS = ("live-actor-identity", "logical-commit", "control-release",
          "rendered-motion", "engine-boundary", "frame-pacing")
FAULTS = tuple(KIND + ":" + name for name in (
    "absent-subject", "missing-control", "wrong-stop-reply", "idle-facing-change"))
CONTRACT = {
    "live-actor-identity": [_spec("follower-stop-stantler-identity", [1, "FOLLOWER", 234, 1, 1])],
    "logical-commit": [_spec("follower-stop-genuine-walk-commits", minimum=1)],
    "control-release": [_spec("follower-stop-released-idle-control", [0, 0])],
    "rendered-motion": [_spec("follower-stop-idle-facing-changes", 0)],
    "engine-boundary": [_spec("follower-stop-empty-replies-with-no-direction", minimum=1)],
    "frame-pacing": [_spec("follower-stop-contiguous-idle-frames", minimum=IDLE_FRAMES)],
}


def contract():
    return deepcopy(CONTRACT)


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    need(replay.get("passed") is True and replay.get("failures") == []
         and meter.get("passed") is True and meter.get("failures") == [],
         "Stantler follower stop replay failed")
    need(record.get("sessionCleanup") == {"sessionId": record.get("sessionId"),
                                          "closed": True, "errors": []},
         "owned session cleanup is missing")
    subject = meter["subjects"]["stantler"]
    actor = next(a for a in meter["terminal"]["actors"] if a.get("handle") == subject["handle"])
    idle = meter["idle"]
    actual = {
        "follower-stop-stantler-identity": [1, actor["role"], actor["species"],
                                           int(actor["identityVerified"]), int(actor["presentationAttached"])],
        "follower-stop-genuine-walk-commits": len(meter["walks"]),
        "follower-stop-released-idle-control": [actor["inputOwnership"], actor["reservationId"]],
        "follower-stop-idle-facing-changes": sum(a["facing"] != b["facing"] for a, b in zip(idle, idle[1:])),
        "follower-stop-empty-replies-with-no-direction": sum(r["frame"] >= idle[0]["frame"] for r in meter["policyReplies"]),
        "follower-stop-contiguous-idle-frames": len(idle),
    }
    rows = []
    for claim, specs in CONTRACT.items():
        for spec in specs:
            value = actual[spec["name"]]
            expected = spec.get("expected", spec.get("minimum"))
            need(value == expected if spec["operator"] == "eq" else value >= expected,
                 "metric differs: " + spec["name"])
            rows.append({"claim": claim, "name": spec["name"], "value": deepcopy(value),
                         "operator": spec["operator"], "expected": deepcopy(expected), "passed": True})
    return rows


class FollowerStopNegative:
    def __init__(self, fault):
        need(fault in FAULTS, "unknown follower stop copied-data fault")
        self.fault, self.applied = fault, False
        self.walk_started = False
        self.completed_frame = None

    def mutate(self, row, subjects):
        if self.applied:
            return row
        changed = deepcopy(row)
        handle = subjects.get("stantler", {}).get("handle", {}).get("value")
        if self.fault.endswith(":idle-facing-change"):
            for event in changed.get("events", []):
                data = event.get("data", {})
                if event.get("kind") != "native" or data.get("actorHandle") != handle:
                    continue
                if data.get("event") == "MOTION_STARTED" and data.get("valueA") == 1:
                    self.walk_started = True
                elif data.get("event") == "CONTROL_RETURNED" and self.walk_started:
                    self.completed_frame = event["frame"]
        if self.fault.endswith((":absent-subject", ":idle-facing-change")):
            for sample in changed.get("samples", []):
                actor = next((a for a in sample.get("actors", []) if a.get("handle", {}).get("value") == handle), None)
                if actor is None:
                    continue
                if self.fault.endswith(":absent-subject"):
                    sample["actors"].remove(actor)
                elif self.completed_frame is not None and sample["frame"] > self.completed_frame \
                        and actor.get("motionKind") == "NONE" and actor.get("motionPhase") == "IDLE":
                    actor["engineObject"]["facing"] ^= 1
                    actor["engineObject"]["movement_cmd"] = 255
                else:
                    continue
                self.applied = True
                return changed
        for event in changed.get("events", []):
            data = event.get("data", {})
            if event.get("kind") == "native" \
                    and data.get("actorHandle") == handle and data.get("event") == "MOTION_STARTED" \
                    and data.get("valueA") == 1:
                self.walk_started = True
            if self.fault.endswith(":missing-control") and event.get("kind") == "native" \
                    and data.get("actorHandle") == handle and data.get("event") == "CONTROL_RETURNED" \
                    and self.walk_started:
                data["event"] = "WORLD_EFFECT"
                data["eventId"] = 14
                self.applied = True
            if self.fault.endswith(":wrong-stop-reply") and self.walk_started \
                    and event.get("kind") == "native-observation" \
                    and data.get("observation") == "walk-policy" and data.get("slot") == 7 and data.get("operation") == 1:
                request, response = bytes.fromhex(data["requestHex"]), bytearray.fromhex(data["responseHex"])
                if request[10] == 255 and response[16] == 0 and response[20] & 8:
                    response[18] = 0
                    data["responseHex"] = response.hex()
                    self.applied = True
                    return changed
        return changed if self.applied else row


def validate_negative_result(result, fault):
    need(fault in FAULTS and result.get("passed") is False and result.get("failures"),
         "follower stop copied-data control did not fail")
    failures = result.get("measurements", {}).get(KIND, {}).get("failures", [])
    expected = {"absent-subject": ("selected handle must name exactly one current active actor", "Stantler follower is absent or ambiguous"),
                "missing-control": ("Stantler has no coherent genuine Walk start", "Stantler Walk has no paired commit/control"),
                "wrong-stop-reply": ("empty follower stop reply requested a direction",),
                "idle-facing-change": ("idle Stantler changed facing without a face command",)}[fault.rsplit(":", 1)[1]]
    need(any(reason in f for reason in expected for f in failures),
         "follower stop control failed for a different rule")
