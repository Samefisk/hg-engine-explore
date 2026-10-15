"""One natural Ram ledge crossing, using the shared Ram and motion readers."""
from copy import deepcopy
from tools.overworld.devtools_profile_feature_measurement import ProfileFeatureMeasurement, require
from tools.overworld.devtools_ram_until_crash_measurement import RamUntilCrashMeasurement, RAM_MASK

KIND = "ram-ledge-continuity-v1"
REQUIREMENT = "current.ram-ledge-continuity"
# Committed heading/momentum and Linear elapsed/carry/mode/cap; proposals and
# engine stream receipts can change while the accepted Hop owns movement.
MOMENTUM = tuple(range(8)) + (25, 32, 33, 34, 35)


def validate_recipe(test):
    setup = (("teleport", {"map": 33, "x": 590, "z": 395, "facing": 1}),
             ("party", {"slot": 0, "species": 155, "level": 10}),
             ("spawn", {"species": 155, "form": 0, "role": "follower", "slot": 0, "level": 10}),
             ("spawn", {"species": 95, "form": 0, "role": "wild", "level": 5, "x": 590, "z": 393}),
             ("bind", {"subject": "onix"}))
    start = {"kind": "measurement-stage", "measurement": KIND, "stage": "charge-started", "when": "final"}
    done = {"kind": "measurement-complete", "measurement": KIND, "when": "final"}
    require(tuple((a["op"], a["args"]) for a in test["setup"]) == setup
            and tuple((a["op"], a["args"]) for a in test["actions"]) == (
                ("step", {"frames": 64, "keys": [], "until": start}),
                ("step", {"frames": 16, "keys": ["RIGHT"], "until": {
                    "kind": "player-field", "path": "x", "operator": "eq", "value": 591, "when": "final"}}),
                ("step", {"frames": 16, "keys": [], "until": {
                    "kind": "player-settled-at", "map": 33, "x": 591, "z": 395, "when": "final"}}),
                ("step", {"frames": 120, "keys": [], "until": done}))
            and test["budgets"]["maxFrames"] == 240,
            "Ram ledge fixture or normal Right dodge differs")


class RamLedgeMeasurement(RamUntilCrashMeasurement):
    def __init__(self, kind=KIND, test=None, max_frames=240):
        super().__init__(kind, test, max_frames)
        self.hop = self.resumed = self.hop_momentum = None
        self.hop_samples = []

    def _sample(self, snapshot, actors):
        actor, frame = actors["onix"], snapshot["frame"]
        require(snapshot["context"] == self.initial["context"] and snapshot["context"]["mapId"] == 33,
                "Ram ledge changed field context")
        events = [e for e in self.current_events if e.get("kind") == "native"
                  and e.get("data", {}).get("actorHandle") == actor["handle"]["value"]]
        for event in events:
            data = event["data"]
            require(data.get("actor") == {k: v for k, v in actor["handle"].items() if k != "value"}
                    and data.get("actorFrame") == snapshot["actorFrame"] and event["frame"] == frame,
                    "Ram ledge native event has a stale full owner")
        for condition in self.conditions:
            if condition["triggered"] and self.trigger is None:
                require(condition["untilCrash"] and condition["active"] and not condition["timed"]
                        and condition["activeUntil"] == 0 and condition["targetKind"] == 1,
                        "Ram ledge did not capture Until Crash Player")
                self.trigger = deepcopy(condition)
        if self.trigger is not None:
            require(actor["matchedLayerMask"] & RAM_MASK, "Ram ended across a successful ledge")
            require(not any(e["data"].get("event") == "MOTION_CANCELED" or (
                e["data"].get("event") == "WORLD_EFFECT" and e["data"].get("valueA") == 3)
                for e in events), "Ram ledge canceled or published Crash")
            self._policy(snapshot, actor)
            self._cooldown(snapshot, actor)
            for event in events:
                data = event["data"]
                if data.get("event") != "MOTION_STARTED": continue
                origin = [actor["origin"][k] for k in ("x", "y")]
                target = [actor["target"][k] for k in ("x", "y")]
                require(data.get("valueB") == actor["motionDuration"] and actor["reservationId"] != 0,
                        "Ram ledge has no accepted motion owner")
                if self.first_walk is None:
                    require(actor["motionKind"] == "WALK" and origin == [590, 393] and target == [590, 394]
                            and data.get("valueA") == 1 and 0 <= frame-self.trigger["frame"] <= 1,
                            "Ram ledge initial South Walk differs")
                    self.first_walk, self.heading = deepcopy(event), 1
                elif actor["motionKind"] == "HOP":
                    require(self.hop is None and origin == [590, 395] and target == [590, 397]
                            and data.get("valueA") == 2, "Ram ledge did not keep its South heading")
                    commits = [e["data"] for e in self.current_events if e.get("kind") == "native-observation"
                               and e.get("data", {}).get("observation") == "walk-policy"
                               and e["data"].get("slot") == actor["handle"]["slot"] and e["data"].get("operation") == 3]
                    require(len(commits) == 1, "Ram ledge lacks its preceding actual Walk commit")
                    policy = bytes.fromhex(commits[0]["policyAfterHex"])
                    lane = bytes.fromhex(commits[0]["laneHex"])
                    require(len(policy) == 36 and policy[0] == 1 and policy[2] > 0 and policy[32] > 0
                            and policy[34] == 1 and len(lane) == 80 and lane[9] == 2
                            and lane[12] == 1 and lane[55] == 0,
                            "Ram ledge preceding policy or legal ledge lane differs")
                    self.hop_momentum, self.hop = policy, deepcopy(event)
                else:
                    require(actor["motionKind"] == "WALK" and data.get("valueA") == 1
                            and target == [origin[0], origin[1]+1], "Ram ledge turned after landing")
                    if self.hop is not None and self.resumed is None:
                        require(origin == [590, 397] and target == [590, 398], "Ram ledge resumed a different tile")
                        inputs = [e["data"] for e in self.current_events if e.get("kind") == "native-observation"
                                  and e.get("data", {}).get("observation") == "walk-policy"
                                  and e["data"].get("slot") == actor["handle"]["slot"] and e["data"].get("operation") == 1]
                        before = [bytes.fromhex(e["policyBeforeHex"]) for e in inputs
                                  if bytes.fromhex(e["responseHex"])[16] == 2]
                        require(before and all(len(p) == 36 and all(p[i] == self.hop_momentum[i] for i in MOMENTUM)
                                               for p in before), "Ram ledge reset accumulated acceleration")
                        self.resumed = deepcopy(event)
            if self.hop is not None and self.resumed is None:
                policy = actor["movementPolicy"]
                require(policy["direction"] == 1 and policy["speed"] == self.hop_momentum[2]
                        and policy["base"] == self.hop_momentum[3], "Ram lost speed or heading during Hop")
                self.hop_samples.append(frame)
        ProfileFeatureMeasurement._sample(self, snapshot, actors)

    def _paired(self, kind, origin, target):
        for motion in self.motion.completed:
            if motion["kind"] != kind or motion["origin"] != origin or motion["target"] != target \
                    or not self._complete_motion(motion): continue
            sequence, receipt = 0, []
            for name in ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"):
                matches = [e for e in self._events(name, actor_name="onix")
                           if motion["startFrame"] <= e["frame"] <= motion["finishFrame"]
                           and e["data"]["sequence"] > sequence]
                if name == "MOTION_STARTED":
                    matches = [e for e in matches if e["data"].get("valueA") == (2 if kind == "HOP" else 1)]
                elif name == "CONTROL_RETURNED":
                    matches = [e for e in matches if e["data"].get("valueA") == 0
                               and e["data"].get("valueB") == motion["commitAfter"]]
                else:
                    matches = [e for e in matches if e["data"].get("valueA") == motion["commitAfter"]]
                if not matches: break
                event = min(matches, key=lambda e: e["data"]["sequence"])
                sequence = event["data"]["sequence"]; receipt.append(deepcopy(event))
            else: return {"motion": deepcopy(motion), "events": receipt}
        return None

    @property
    def ready(self):
        hop = self._paired("HOP", [590, 395], [590, 397])
        resume = self._paired("WALK", [590, 397], [590, 398])
        return bool(self.trigger and self.hop and self.resumed and hop and resume and self.policy_calls
                    and 0 <= self.resumed["frame"]-hop["motion"]["finishFrame"] <= 1
                    and self.resumed["data"]["sequence"] > hop["events"][-1]["data"]["sequence"])

    def finish(self):
        return ProfileFeatureMeasurement.finish(self)

    def result(self):
        return {**ProfileFeatureMeasurement.result(self), "trigger": deepcopy(self.trigger),
                "firstWalk": deepcopy(self.first_walk), "hop": deepcopy(self.hop),
                "resumed": deepcopy(self.resumed), "heading": self.heading,
                "policyCalls": deepcopy(self.policy_calls), "hopMomentumHex": self.hop_momentum.hex() if self.hop_momentum else None,
                "hopSamples": list(self.hop_samples), "completeHop": self._paired("HOP", [590, 395], [590, 397]),
                "completeResumedWalk": self._paired("WALK", [590, 397], [590, 398])}
