"""One free baby Cargo completes its authored Flee away from its claimant.

Uses existing completed-queue bindings, resolver cache, events and MotionRecorder.
Prepared placement and Player-notice Skittish movement earn no credit.
"""
from copy import deepcopy
import struct

from scripts.overworld_behavior_profile_viewer import _stable_condition_id
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_profile_feature_measurement import application_index, decode_condition
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel

KIND = "throw-cargo-flee-v1"
REQUIREMENT = "current.throw-cargo-flees-actual-pursuer"
APPLICATION = application_index("apply-skittish")
CONDITION = _stable_condition_id("skittish", "condition-baby-targeted-for-pickup")
BOUNDARY = "main-task-queue-completion"
SUBJECTS = (("cargo", 173), ("geodude", 74))
SETUP = (("throw-tile", "teleport", {"map": 33, "x": 585, "z": 407, "facing": 1}),
         ("spawn-cargo", "spawn", {"species": 173, "form": 0, "role": "wild", "level": 5, "x": 587, "z": 402}),
         ("bind-cargo", "bind", {"subject": "cargo"}),
         ("spawn-geodude", "spawn", {"species": 74, "form": 0, "role": "wild", "level": 5, "x": 584, "z": 404}),
         ("bind-geodude", "bind", {"subject": "geodude"}))
ACTION = ("natural-claim-and-flee", "step", {"frames": 240, "keys": [],
          "until": {"kind": "measurement-complete", "measurement": KIND, "when": "final"}})


def require(value, message):
    if not value:
        raise ValueError("Cargo Flee: " + message)


def validate_recipe(test):
    require(test["id"] == "wild.throw-cargo-flee" and test["mode"] == "prepared"
            and test["requirements"] == [REQUIREMENT]
            and test["subjects"] == [dict(id=n, species=s, role="WILD", acquire="spawn") for n,s in SUBJECTS]
            and tuple((a["id"], a["op"], a["args"]) for a in test["setup"]) == SETUP
            and [(a["id"], a["op"], a["args"]) for a in test["actions"]] == [ACTION]
            and test["assertions"] == [{"kind": "measurement-complete", "measurement": KIND, "when": "final"}]
            and test["budgets"]["maxFrames"] == 600 and test["budgets"]["minObservedFrames"] == 2,
            "bounded natural fixture differs")


class ThrowCargoFleeMeasurement:
    def __init__(self, source):
        self.source = source
        self.latest = None
        self.subjects = {}
        self.setup_index = self.observed_frames = 0
        self.failures = []
        self.condition = self.witness = self.completed = None
        self.motion = MotionRecorder()
        self.events = []

    def _boundary(self, sample, fixture=True):
        require(sample.get("fieldAvailable") is True and sample.get("observationBoundary") == BOUNDARY
                and sample.get("romSha256") == self.source["romSha256"]
                and sample.get("fieldControl", {}).get("taskPointer") == 0,
                "missing completed field queue or battle")
        if fixture:
            require(sample.get("context", {}).get("mapId") == 33, "left Route29")

    def _actor(self, sample, name):
        selected = select_current_actor(sample, self.subjects[name])
        return next(a for a in sample["actors"] if a["handle"] == selected["handle"])

    def _claim(self, sample, cargo, pursuer):
        combat = sample.get("pokemonCombat", {})
        interactions = combat.get("interactions", {})
        require(combat.get("available") is True and combat.get("frame") == sample["frame"]
                and combat.get("nativeCycle") == sample["nativeCycle"]
                and combat.get("identity", {}).get("romSha256") == self.source["romSha256"]
                and combat["identity"].get("overlaySha256") == self.source["overlaySha256"]
                and interactions.get("available") is True and interactions.get("schemaVersion") == 1
                and interactions.get("frame") == sample["frame"]
                and interactions.get("nativeCycle") == sample["nativeCycle"]
                and interactions.get("observationBoundary") == BOUNDARY
                and interactions.get("fieldSystem") == sample["fieldControl"].get("fieldPointer")
                and interactions.get("identity", {}).get("romSha256") == self.source["romSha256"],
                "claim receipt is absent, stale or unauthenticated")
        rows = [r for r in interactions.get("carriers", []) if r.get("handle") == pursuer["handle"]]
        require(len(rows) == 1 and rows[0].get("available") is True and rows[0].get("role") == "WILD",
                "claimant has no full-current binding receipt")
        row = rows[0]; raw = bytes.fromhex(row.get("rawBindingsHex", ""))
        require(len(raw) == 60 and raw[:12] == raw_handle(pursuer["handle"]), "claimant binding owner differs")
        state = interactions["throwState"]; native = bytes.fromhex(state["rawHex"])
        require(len(native) == 16 and list(native[:10]) == state["targets"]
                and struct.unpack_from("<3H", native, 10) ==
                    (state["targetMask"], state["carrierMask"], state["recoveringMask"]),
                "native claim masks differ")
        encoded = native[pursuer["handle"]["slot"]]
        if encoded == 0:
            return False
        # Other legitimate selections are not a witness for this exact Cargo.
        if (encoded & 63) != cargo["handle"]["slot"] + 1:
            return False
        binding = row["bindings"]["cargo"]; data = raw[36:60]
        require(binding.get("bound") is True and binding.get("targetCurrent") is True
                and binding.get("target") == dict(kind="ACTOR", actor=cargo["handle"])
                and data.hex() == binding.get("rawHex") and data[:12] == raw_handle(cargo["handle"])
                and data[12:14] == bytes([2,0]) and data[22] == binding.get("flags") and data[22] != 0
                and bool(state["targetMask"] & (1 << cargo["handle"]["slot"]))
                and bool(state["carrierMask"] & (1 << pursuer["handle"]["slot"])),
                "claim is stale or does not bind the exact Cargo")
        return not encoded & 192  # Free selected Cargo, before carry or windup.

    def _profile(self, sample, cargo, pursuer, cache):
        require(isinstance(cache, dict) and cache.get("frame", -1) >= sample["frame"]
                and cache.get("nativeCycle", -1) >= sample["nativeCycle"]
                and sample.get("nativeObservation", {}).get("coverageComplete") is True
                and sample["nativeObservation"].get("profilesEvicted") == 0
                and cargo["behaviorFingerprint"] in sample["nativeObservation"].get("profileFingerprints", []),
                "Flee profile has no coherent native cache")
        rows = [r for r in cache.get("resolvedProfiles", [])
                if r.get("resolved") is True and r.get("fingerprint") == cargo["behaviorFingerprint"]]
        require(len(rows) == 1 and rows[0].get("sourceSha256") == self.source["profileSha256"],
                "Flee profile differs from sealed authored source")
        data = bytes.fromhex(rows[0]["resultHex"])
        require(len(data) == 216 and data[0] == 4 and data[13] == 3
                and struct.unpack_from("<I", data, 192)[0] == cargo["behaviorFingerprint"]
                and data[196:210] == raw_handle(pursuer["handle"]) + bytes([2,0])
                and data[212] == APPLICATION and data[213] == 0
                and struct.unpack_from("<H", data, 214)[0] == CONDITION,
                "Flee resolved target is not the full-current actual pursuer")

    def _sample(self, sample, events, cache):
        self._boundary(sample)
        cargo = self._actor(sample, "cargo"); pursuer = self._actor(sample, "geodude")
        require(cargo["handle"] != pursuer["handle"], "Cargo and claimant are the same actor")
        claim = self._claim(sample, cargo, pursuer)
        for event in events:
            data = event.get("data", {})
            if event.get("kind") == "trace-status":
                require(data.get("code") not in ("unread-events-lost", "sequence-reset", "invalid-native-ring", "trace-filter-changed")
                        and data.get("unreadEventsLost", 0) == 0 and data.get("coverageComplete", True) is True,
                        "semantic trace is incomplete")
            if event.get("kind") != "native" or data.get("actorHandle") != cargo["handle"]["value"]:
                continue
            require(data.get("actor") == {k:v for k,v in cargo["handle"].items() if k != "value"}
                    and type(data.get("sequence")) is int, "stale Cargo semantic event")
            if data.get("event") == "CONDITIONAL_RESOLVED":
                decoded = decode_condition(event)
                if decoded["conditionId"] == CONDITION and decoded["active"]:
                    require(claim and decoded["truth"] and decoded["activationMode"] == "while-true"
                            and decoded["application"] == APPLICATION and decoded["targetSourceApplication"] == APPLICATION
                            and decoded["targetKind"] == 2 and decoded["targetSlot"] == pursuer["handle"]["slot"],
                            "targeted Flee condition does not name the actual claimant")
                    self.condition = deepcopy(decoded)
            # Travel uses the completed game frame; actorFrame keeps the trace clock.
            self.events.append(dict(data, frame=sample["frame"]))
        moving = cargo["motionKind"] in ("WALK", "HOP") and cargo["motionPhase"] in ("PLANNED", "MOVING")
        if self.witness is None and claim and self.condition is not None and moving and cargo["motionElapsed"] in (0,1):
            require(cargo["matchedLayerMask"] & (1 << APPLICATION), "Flee application is not resolved")
            self._profile(sample, cargo, pursuer, cache)
            origin = [cargo["origin"][k] for k in ("x", "y")]
            target = [cargo["target"][k] for k in ("x", "y")]
            anchor = [pursuer["logical"][k] for k in ("x", "y")]
            distance = lambda point: max(abs(point[i]-anchor[i]) for i in (0,1))
            require(distance(target) > distance(origin)
                    and sum((target[i]-origin[i]) * (origin[i]-anchor[i]) for i in (0,1)) > 0,
                    "movement does not go away from the actual pursuer")
            self.witness = dict(startFrame=sample["frame"], cargo=deepcopy(cargo["handle"]),
                                pursuer=deepcopy(pursuer["handle"]), pursuerTile=anchor,
                                origin=origin, target=target, condition=deepcopy(self.condition))
        if self.witness is not None and self.completed is None:
            require(claim, "actual pursuer claim ended before Flee completed")
            self._profile(sample, cargo, pursuer, cache)
            self.motion.observe(sample["frame"], cargo, cargo["engineObject"])
            require(not self.motion.failures, "Flee native travel failed: " + str(self.motion.failures))
            if self.motion.completed:
                complete = self.motion.completed[0]
                require(complete["kind"] in ("WALK", "HOP") and complete_travel(complete)
                        and complete["origin"] == self.witness["origin"] and complete["target"] == self.witness["target"],
                        "Flee did not complete its admitted movement")
                names = {e["event"] for e in self.events if self.witness["startFrame"] <= e["frame"] <= complete["finishFrame"]}
                require({"INTENT_CREATED", "MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"} <= names,
                        "Flee completed movement lacks intent, commit or control return")
                self.completed = deepcopy(complete)
        self.latest = deepcopy(sample)
        self.observed_frames += 1

    def observe_record(self, row, on_sample=None):
        try:
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase") == "setup", "initial boundary differs")
                self._boundary(row["initialSnapshot"], False); self.latest = deepcopy(row["initialSnapshot"])
                return self.result()
            if row.get("phase") == "setup":
                require(self.setup_index < len(SETUP) and row.get("action") == SETUP[self.setup_index][0]
                        and row.get("command") == SETUP[self.setup_index][1], "setup order differs")
                sample = row["snapshot"]; self._boundary(sample)
                if row["command"] == "bind":
                    name = SETUP[self.setup_index][2]["subject"]
                    selected = select_current_actor(sample, row["receipt"])
                    require((selected["species"], selected["role"]) == (dict(SUBJECTS)[name], "WILD"), "bound species or role differs")
                    self.subjects[name] = deepcopy(row["receipt"])
                self.latest = deepcopy(sample); self.setup_index += 1
                return self.result()
            require(self.setup_index == len(SETUP) and row.get("phase") == "observe"
                    and row.get("action") == ACTION[0] and "command" not in row, "observation order differs")
            for sample, events, _ in validate_raw_chunk(row, self.latest):
                require(self.observed_frames < ACTION[2]["frames"], "natural frame limit exceeded")
                self._sample(sample, events, row.get("profileCache"))
                if on_sample: on_sample(sample, self.observed_frames)
        except (ValueError, KeyError, TypeError, StopIteration, struct.error) as error:
            self.failures.append(str(error))
        return self.result()

    def result(self):
        ready = not self.failures and self.completed is not None
        return dict(kind=KIND, requirements=[REQUIREMENT], ready=ready, passed=ready, acceptedProof=False,
                    observedFrames=self.observed_frames, observedFrameUnit="completed-game-frame",
                    subjects=deepcopy(self.subjects), witness=deepcopy(self.witness),
                    completedMotion=deepcopy(self.completed), failures=list(self.failures))

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("Cargo Flee: no completed targeted movement away from actual pursuer")
        return self.result()
