"""One prepared Wild Clefairy Appear Hop through its final restore."""
from copy import deepcopy

from tools.overworld.devtools_records import engine_binding_identity, select_current_actor
from tools.overworld.normal_play_observer import live_identity


KIND = "appear-hop-timing-v1"
REQUIREMENT = "shared.appear-hop-timing-v1"
JUMP_COMMANDS = frozenset((48, 49, 50, 51))
DELAY_COMMAND = 62
RESTORE_COMMAND = 74
IDLE_COMMAND = 255
IDENTITY = (
    "handle", "species", "form", "level", "role", "subjectIdentity",
    "authorityGeneration", "engineAnchorGeneration", "presentationGeneration",
    "behaviorFingerprint", "matchedLayerMask",
)


def require(value, reason):
    if not value:
        raise ValueError(reason)


class AppearHopMeasurement:
    def __init__(self, max_frames=30):
        require(type(max_frames) is int and 14 <= max_frames <= 60,
                "invalid Appear Hop frame bound")
        self.max_frames = max_frames
        self.initial = self.last = self.terminal = self.subject = self.actor = None
        self.frames = 0
        self.stage = 0
        self.restore_frame = None
        self.failures = []
        self.samples = []

    def _select_initial(self, snapshot):
        candidates = [actor for actor in snapshot.get("actors", [])
                      if actor.get("active") is True
                      and actor.get("species") == 35
                      and actor.get("role") == "WILD"
                      and actor.get("controllerState") == 1
                      and actor.get("engineObject", {}).get("movement_cmd") in JUMP_COMMANDS]
        require(len(candidates) == 1,
                "Appear Hop needs one live Wild Clefairy in its jump command")
        actor = candidates[0]
        require(live_identity(
                    actor, actor.get("sourceIdentity", {}), actor.get("engineIdentity", {}),
                    species=35, role="WILD",
                    current_epoch=snapshot["context"]["fieldEpoch"])
                and actor.get("identityVerified") is True
                and actor.get("presentationAttached") is True
                and actor.get("inputOwnership") == 0
                and actor.get("motionKind") == "NONE"
                and actor.get("motionPhase") == "IDLE",
                "Appear Hop Clefairy identity or presentation differs")
        self.subject = select_current_actor(snapshot, actor)
        self.actor = deepcopy(actor)
        self.initial = deepcopy(snapshot)
        return actor

    def _select_current(self, snapshot):
        selected = select_current_actor(snapshot, self.subject)
        actor = next(item for item in snapshot["actors"]
                     if item["handle"] == selected["handle"])
        require(all(actor.get(key) == self.actor.get(key) for key in IDENTITY)
                and actor.get("sourceIdentity") == self.actor.get("sourceIdentity")
                and engine_binding_identity(actor.get("engineIdentity"))
                    == engine_binding_identity(self.actor.get("engineIdentity"))
                and snapshot["context"] == self.initial["context"],
                "Appear Hop Clefairy identity or owner changed")
        return actor

    def observe(self, snapshot, events):
        del events
        if self.failures:
            return self.result()
        try:
            actor = self._select_initial(snapshot) if self.initial is None \
                else self._select_current(snapshot)
            if self.last is not None:
                require(snapshot.get("observationBoundary") == "main-task-queue-completion"
                        and snapshot["frame"] == self.last["frame"] + 1
                        and snapshot["nativeCycle"] >= self.last["nativeCycle"],
                        "Appear Hop completed frame stream has a gap")
            selector = snapshot.get("selector", {})
            require(all(type(selector.get(key)) is int and selector[key] == 0
                        for key in ("heldKeys", "newKeys", "physicalPressed", "simulatedKeys")),
                    "Appear Hop timing requires neutral input")
            require(actor.get("presentationAttached") is True
                    and actor.get("motionKind") == "NONE"
                    and actor.get("motionPhase") == "IDLE",
                    "Appear Hop actor presentation or shared motion changed")
            self.frames += 1
            require(self.frames <= self.max_frames,
                    "Appear Hop did not return control within 30 frames")
            engine = actor["engineObject"]
            command = engine["movement_cmd"]
            state = actor["controllerState"]
            require(type(command) is int and type(state) is int,
                    "Appear Hop command or controller state is missing")
            if self.stage == 0:
                if command == DELAY_COMMAND:
                    self.stage = 1
                else:
                    require(command in JUMP_COMMANDS,
                            "Appear Hop jump command order differs")
            if self.stage == 1:
                if command == RESTORE_COMMAND:
                    self.stage = 2
                    self.restore_frame = snapshot["frame"]
                else:
                    require(command == DELAY_COMMAND,
                            "Appear Hop delay/restore command order differs")
            elif self.stage == 2:
                if command == IDLE_COMMAND:
                    require(self.last is not None
                            and self.last["actors"]
                            and self.samples[-1]["command"] == RESTORE_COMMAND,
                            "Appear Hop restore did not finish on the next completed frame")
                    require(state == 0,
                            "Appear Hop stayed locked after its final restore")
                    self.stage = 3
                    self.terminal = deepcopy(snapshot)
                else:
                    require(command == RESTORE_COMMAND,
                            "Appear Hop restore command order differs")
            if self.stage < 3:
                require(state == 1,
                        "Appear Hop released control before its final restore")
            self.samples.append({
                "frame": snapshot["frame"],
                "command": command,
                "step": engine["movement_step"],
                "faceY": engine["face_y"],
                "controllerState": state,
            })
            require(len(self.samples) <= self.max_frames,
                    "Appear Hop sample bound exceeded")
            self.last = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    @property
    def ready(self):
        return self.stage == 3 and not self.failures

    @property
    def closed(self):
        return self.ready

    def finish(self):
        if not self.ready and not self.failures:
            self.failures.append("Appear Hop did not complete")
        if self.ready and not any(sample["faceY"] > 0 for sample in self.samples):
            self.failures.append("Appear Hop has no rendered vertical arc")
        return self.result()

    def result(self):
        return {
            "kind": KIND,
            "requirements": [REQUIREMENT],
            "passed": self.ready,
            "ready": self.ready,
            "closed": self.closed,
            "acceptedProof": False,
            "failures": list(self.failures),
            "frames": self.frames,
            "subject": deepcopy(self.subject),
            "initial": deepcopy(self.initial),
            "terminal": deepcopy(self.terminal),
            "restoreFrame": self.restore_frame,
            "samples": deepcopy(self.samples),
        }
