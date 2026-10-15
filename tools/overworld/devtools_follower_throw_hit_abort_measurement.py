"""A real Ram hit retires a pre-Cargo Follower Throw capture and permits rebind."""

from copy import deepcopy

from tools.overworld.devtools_profile_feature_measurement import (
    ProfileFeatureMeasurement, application_index, require,
)
from tools.overworld.devtools_records import select_current_actor


KIND = "follower-throw-hit-abort-v1"
REQUIREMENT = "current.follower-throw-hit-abort"
NOTICE = 12365
CARGO = 26783
THROW_APP = application_index("apply-throw")
RAM_APP = application_index("apply-ram")
MAX_FRAMES = 420
STABLE_FRAMES = 8


def validate_recipe(test):
    require(test["id"] == "follower.throw-hit-abort"
            and test["mode"] == "prepared"
            and test["measurements"] == [{"kind": KIND, "subject": "mankey"}]
            and test["subjects"] == [
                {"id": "mankey", "species": 56, "role": "FOLLOWER", "acquire": "existing"},
                {"id": "onix", "species": 95, "role": "WILD", "acquire": "spawn"}]
            and [(a["id"], a["op"], a["args"]) for a in test["setup"]] == [
                ("ram-line", "teleport", {"map": 33, "x": 607, "z": 402, "facing": 2}),
                ("prepare-mankey", "party", {"slot": 0, "species": 56, "level": 20}),
                ("create-mankey", "spawn", {"species": 56, "form": 0,
                                              "role": "follower", "slot": 0, "level": 20}),
                ("settle-mankey", "step", {"frames": 32, "keys": [], "until": {
                    "kind": "follower-settled", "species": 56, "partySlot": 0, "when": "final"}}),
                ("spawn-onix", "spawn", {"species": 95, "form": 0,
                                          "role": "wild", "level": 5, "x": 602, "z": 402}),
                ("bind-mankey", "bind", {"subject": "mankey"}),
                ("bind-onix", "bind", {"subject": "onix"}),
            ]
            and len(test["actions"]) == 1
            and test["actions"][0]["op"] == "step"
            and test["actions"][0]["args"] == {"frames": MAX_FRAMES, "keys": [], "until": {
                "kind": "measurement-complete", "measurement": KIND, "when": "final"}}
            and test["budgets"]["maxFrames"] <= 500
            and test["budgets"]["minObservedFrames"] >= 32,
            "Follower Throw hit-abort fixture differs")


def _native(snapshot, mankey):
    combat = snapshot.get("pokemonCombat", {})
    interaction = combat.get("interactions", {})
    require(combat.get("schemaVersion") == interaction.get("schemaVersion") == 1
            and combat.get("available") is interaction.get("available") is True
            and combat.get("frame") == interaction.get("frame") == snapshot["frame"]
            and combat.get("nativeCycle") == interaction.get("nativeCycle") == snapshot["nativeCycle"]
            and combat.get("observationBoundary") == interaction.get("observationBoundary")
                == "main-task-queue-completion"
            and combat.get("identity", {}).get("romSha256")
                == interaction.get("identity", {}).get("romSha256") == snapshot["romSha256"],
            "Follower Throw hit lacks a current native combat and binding read")
    targets = [t for t in combat.get("targets", []) if t.get("handle") == mankey["handle"]]
    carriers = [r for r in interaction.get("carriers", []) if r.get("handle") == mankey["handle"]]
    require(len(targets) == len(carriers) == 1
            and targets[0].get("role") == carriers[0].get("role") == "FOLLOWER"
            and targets[0].get("species") == 56 and carriers[0].get("available") is True
            and targets[0].get("hpMirrorMatches") is True
            and targets[0].get("hpSource") == "party"
            and targets[0].get("hp") == targets[0].get("currentHp")
            and targets[0].get("actualMaxHp") == targets[0].get("maxHp")
            and isinstance(targets[0].get("maxHp"), int) and targets[0]["maxHp"] > 0,
            "Follower Throw native carrier or party HP owner differs")
    return targets[0], carriers[0]


def _notice(snapshot, mankey):
    data = snapshot.get("pokemonAppearance", {})
    require(data.get("schemaVersion") == 1 and data.get("available") is True
            and data.get("frame") == snapshot["frame"]
            and data.get("nativeCycle") == snapshot["nativeCycle"]
            and data.get("observationBoundary") == "main-task-queue-completion"
            and data.get("identity", {}).get("romSha256") == snapshot["romSha256"],
            "Follower Throw lacks its current native condition read")
    conditions = data.get("conditions", {})
    item = conditions.get(str(mankey["handle"]["slot"]),
                          conditions.get(mankey["handle"]["slot"]))
    require(isinstance(item, dict) and item.get("available") is True
            and item.get("frame") == snapshot["actorFrame"]
            and item.get("owner", {}).get("actor", {}).get("handle") == mankey["handle"]
            and item["owner"]["actor"].get("subjectIdentity") == mankey["subjectIdentity"]
            and item["owner"].get("context") == snapshot["context"],
            "Follower Throw condition owner is absent or stale")
    rows = [s for s in item.get("states", [])
            if s.get("application") == THROW_APP and s.get("conditionId") == NOTICE]
    require(len(rows) == 1, "Follower Throw notice state is absent or duplicate")
    return rows[0]


def _current_trigger(carrier, onix, notice):
    bindings = carrier.get("bindings", {})
    trigger = bindings.get("trigger", {})
    handle = onix["handle"]
    return (notice.get("flags", 0) & 1) != 0 \
        and notice.get("targetKind") == 2 \
        and notice.get("targetSlot") == handle["slot"] \
        and notice.get("targetGeneration") == handle["generation"] \
        and notice.get("targetEncounterGeneration") == handle["encounterGeneration"] \
        and trigger.get("bound") is True and trigger.get("targetCurrent") is True \
        and trigger.get("sourceConditionId") == NOTICE \
        and trigger.get("sourceApplication") == THROW_APP \
        and trigger.get("target") == {"kind": "ACTOR", "actor": handle}


def _pre_cargo_capture(carrier, onix, notice):
    cargo = carrier.get("bindings", {}).get("cargo", {})
    throw = carrier.get("throw", {})
    return _current_trigger(carrier, onix, notice) \
        and cargo.get("bound") is False and cargo.get("targetCurrent") is False \
        and cargo.get("target", {}).get("kind") == "NONE" \
        and throw.get("carrier") is False and not throw.get("targetRaw") \
        and throw.get("carried") is False and throw.get("windup") is False


class FollowerThrowHitAbortMeasurement(ProfileFeatureMeasurement):
    def __init__(self, kind=KIND, test=None, max_frames=500):
        super().__init__(kind, test, max_frames)
        self.captured = self.hit = self.cleared = self.rebound = None
        self.post_frames = 0
        self.previous = None
        self.observations = []

    def _discover(self, snapshot):
        found = {}
        for name, species, role in (("mankey", 56, "FOLLOWER"), ("onix", 95, "WILD")):
            actors = [a for a in snapshot.get("actors", []) if a.get("active") is True
                      and a.get("role") == role and a.get("species") == species
                      and a.get("identityVerified") is True
                      and a.get("presentationAttached") is True]
            if len(actors) != 1:
                return False
            found[name] = select_current_actor(snapshot, actors[0])
        self.subjects = found
        self.subject = deepcopy(found["mankey"])
        self.initial = deepcopy(snapshot)
        return True

    @property
    def ready(self):
        return self.rebound is not None and self.post_frames >= STABLE_FRAMES and not self.failures

    @property
    def closed(self):
        return self.ready

    def observe(self, snapshot, events):
        if self.failures:
            return self.result()
        try:
            if not self.subjects and not self._discover(snapshot):
                return self.result()
            require(self.last is None or snapshot["frame"] == self.last["frame"] + 1,
                    "Follower Throw completed-frame stream has a gap")
            require(snapshot.get("fieldAvailable") is True
                    and snapshot.get("observationBoundary") == "main-task-queue-completion"
                    and snapshot.get("context") == self.initial.get("context")
                    and snapshot["context"].get("mapId") == 33
                    and (self.hit is not None
                         or [snapshot["player"]["x"], snapshot["player"]["y"]] == [607, 402])
                    and snapshot.get("fieldControl", {}).get("taskPointer") == 0,
                    "Follower Throw hit left its current Route 29 field")
            actors = self._actors(snapshot)
            mankey, onix = actors["mankey"], actors["onix"]
            require(mankey.get("role") == "FOLLOWER" and onix.get("role") == "WILD",
                    "Follower Throw current actor role differs")
            if self.captured is None:
                require([mankey["logical"]["x"], mankey["logical"]["y"]] == [606, 402]
                        and onix["logical"]["y"] == 402
                        and onix["logical"]["x"] < mankey["logical"]["x"],
                        "Follower Throw pre-hit Ram lane differs")
            self.frames += 1
            require(self.frames <= min(self.max_frames, MAX_FRAMES),
                    "Follower Throw hit exceeded its bounded natural window")
            target, carrier = _native(snapshot, mankey)
            notice = _notice(snapshot, mankey)
            for name in ("trigger", "cargo"):
                binding = carrier.get("bindings", {}).get(name, {})
                if binding.get("bound"):
                    require(binding.get("targetCurrent") is True
                            and binding.get("target") == {"kind": "ACTOR", "actor": onix["handle"]},
                            "Follower Throw bound a stale or different target")
            if carrier.get("throw", {}).get("carrier"):
                require(carrier.get("bindings", {}).get("cargo", {}).get("bound") is True
                        and carrier["bindings"]["cargo"].get("targetCurrent") is True,
                        "Follower Throw retained a claim without current Cargo")
            held = carrier.get("throw", {}).get("carried") is True
            require(not held if self.hit is None else True,
                    "Follower Throw reached HELD before the carrier hit")
            captured = _pre_cargo_capture(carrier, onix, notice)
            current_trigger = _current_trigger(carrier, onix, notice)
            current = {"frame": snapshot["frame"], "mankey": deepcopy(mankey),
                       "onix": deepcopy(onix), "target": deepcopy(target),
                       "carrier": deepcopy(carrier), "notice": deepcopy(notice),
                       "captured": captured, "currentTrigger": current_trigger}
            self.observations.append(current)
            if self.captured is None and captured:
                self.captured = deepcopy(current)
            previous = self.previous
            if previous is not None:
                before = previous["target"]
                now = current["target"]
                if now.get("hitCount", 0) != before.get("hitCount", 0):
                    damage = before.get("currentHp", 0) - now.get("currentHp", 0)
                    require(self.captured is not None and self.hit is None
                            and previous["captured"] is True
                            and before.get("maxHp") == now.get("maxHp")
                            and 0 < damage <= before.get("currentHp", 0)
                            and damage <= max(1, before["maxHp"] // 2)
                            and now.get("lastDamage") == damage
                            and now.get("hitCount") == before.get("hitCount") + 1
                            and now.get("immunityFrames", 0) > 0
                            and previous["onix"].get("matchedLayerMask", 0) & (1 << RAM_APP)
                            and previous["onix"].get("motionKind") == "WALK"
                            and previous["onix"].get("motionPhase") == "MOVING"
                            and previous["mankey"]["logical"] == {"x": 606, "y": 402}
                            and previous["onix"]["logical"]["y"] == 402
                            and previous["onix"]["logical"]["x"] < 606
                            and previous["carrier"].get("throw", {}).get("carried") is False,
                            "Follower Throw lacks one current pre-Cargo Ram hit on its capturing carrier")
                    self.hit = deepcopy(current)
            if self.hit is not None and self.cleared is None:
                bindings = carrier.get("bindings", {})
                if (not bindings.get("trigger", {}).get("bound")
                        and not bindings.get("cargo", {}).get("bound")
                        and not carrier.get("throw", {}).get("carrier")
                        and not carrier.get("throw", {}).get("targetRaw")
                        and not notice.get("flags", 0) & 1):
                    require(snapshot["frame"] <= self.hit["frame"] + 40,
                            "Follower Throw delayed its hit abort")
                    self.cleared = deepcopy(current)
                require(snapshot["frame"] <= self.hit["frame"] + 40,
                        "Follower Throw kept its hit binding or claim")
            elif self.cleared is not None and self.rebound is None and current_trigger:
                require(snapshot["frame"] > self.cleared["frame"]
                        and carrier["bindings"]["trigger"]["target"]["actor"] == onix["handle"],
                        "Follower Throw rebound a different target")
                self.rebound = deepcopy(current)
            if self.rebound is not None and snapshot["frame"] > self.rebound["frame"]:
                require(current_trigger and not held
                        and target.get("currentHp") == self.hit["target"]["currentHp"],
                        "Follower Throw lost its fresh same-target binding after hit")
                self.post_frames += 1
            self.previous = deepcopy(current)
            self.last = deepcopy(snapshot)
            if self.ready:
                self.terminal = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def finish(self):
        if not self.ready and not self.failures:
            self.failures.append("Follower Throw did not hit, clear, and recapture in the natural window")
        return self.result()

    def result(self):
        return {**super().result(), "captured": deepcopy(self.captured),
                "hit": deepcopy(self.hit), "cleared": deepcopy(self.cleared),
                "rebound": deepcopy(self.rebound), "postFrames": self.post_frames,
                "observations": deepcopy(self.observations)}
