"""Exact native WALK crash-presentation evidence; never a pose tolerance."""
from copy import deepcopy

BOUNDARY = "main-task-queue-completion"
HANDLE = ("value", "slot", "generation", "encounterGeneration", "fieldEpoch", "mapGeneration")
# Independent contract table checked against actual C by test_crash_presentation.
OFFSETS = {10:256, 9:-512, 8:512, 7:-256, 6:256, 5:-512, 4:512, 3:-256, 2:256, 1:-512, 0:0}


def integer(value, name, low=0, high=0xFFFFFFFF):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("invalid crash " + name)
    return value


class CrashPresentationMeasurement:
    def __init__(self, *, max_frames=65535):
        # A transition can restore after the first effect sample: two distinct
        # frames per terminated proof. Keep a budget-derived bound plus one
        # final pending start; never silently truncate retained effects.
        self.max_proofs = integer(max_frames, "frame budget", 1, 65535) // 2 + 1
        self.proofs = []
        self._pending = None
        self._preroll_previous = None
        self._failed = False
        self._last = None

    @property
    def ready(self):
        return not self._failed and self._pending is None

    def _metadata(self, snapshot, actor):
        data = actor.get("crashPresentation", {})
        if data.get("known") is not True or data.get("reason") != "observed" \
                or data.get("boundary") != BOUNDARY or data.get("frame") != snapshot["frame"] \
                or data.get("nativeCycle") != snapshot["nativeCycle"]:
            raise ValueError("missing or stale crash presentation metadata")
        integer(data["frame"], "frame"); integer(data["nativeCycle"], "native cycle")
        integer(data["timer"], "timer", 0, 32)
        integer(data["baseX"], "base X", -0x80000000, 0x7FFFFFFF)
        integer(data["baseZ"], "base Z", -0x80000000, 0x7FFFFFFF)
        pointer = integer(data["objectPointer"], "object", 0x02000000, 0x023FFED4)
        if pointer & 3 or data.get("handle") != actor.get("handle"):
            raise ValueError("crash owner mismatch")
        for key in HANDLE:
            integer(data["handle"][key], "handle " + key)
        return data

    def observe(self, snapshot, actor, previous_actor, *, transition=None):
        if self._failed:
            raise ValueError("crash presentation measurement already failed")
        try:
            cycle = integer(snapshot["nativeCycle"], "native cycle")
            if self._last is not None and cycle < self._last["nativeCycle"]:
                raise ValueError("crash native clock moved backwards")
            result = self._observe(snapshot, actor, previous_actor, transition)
            self._last = {"frame":snapshot["frame"], "nativeCycle":cycle,
                          "context":deepcopy(snapshot["context"])}
            return result
        except (ValueError, KeyError, TypeError, IndexError) as error:
            self._failed = True
            raise ValueError("crash presentation invalid: " + str(error)) from error

    def _transition_restore(self, snapshot, actor, previous, data, engine, transition):
        proof = self._pending
        terminal = proof["terminal"]
        if not isinstance(transition, dict) or set(transition) != {"context", "rebound"}:
            raise ValueError("crash transition receipt missing")
        if self._last is None or snapshot["frame"] != self._last["frame"] + 1 \
                or snapshot["frame"] != proof["startFrame"] + len(proof["samples"]):
            raise ValueError("crash transition is not adjacent")
        old_h, new_h = proof["handle"], actor["handle"]
        if previous["handle"] != old_h or self._last["context"] != proof["context"] \
                or any(new_h[k] != old_h[k] for k in ("value", "slot", "generation", "encounterGeneration")) \
                or any(new_h[k] != ((old_h[k]+1) & 65535 or 1) for k in ("fieldEpoch", "mapGeneration")) \
                or any(snapshot["context"][k] != new_h[k] for k in ("fieldEpoch", "mapGeneration")):
            raise ValueError("crash transition owner differs")
        for key in ("species", "role", "subjectIdentity", "motionPhase", "motionKind", "motionElapsed",
                    "motionDuration", "origin", "target", "logical", "commitSequence", "authorityGeneration",
                    "engineAnchorGeneration", "presentationGeneration"):
            if key not in terminal or previous.get(key) != terminal[key] or actor.get(key) != terminal[key]:
                raise ValueError("crash transition terminal or subject changed")
        change, rebound = transition["context"], transition["rebound"]
        for event, name, reason, handle, a, b in (
            (change, "CONTEXT_CHANGED", "CONTEXT_LOST", old_h, old_h["fieldEpoch"], new_h["fieldEpoch"]),
            (rebound, "ACTOR_REBOUND", "OK", new_h, proof["context"]["mapId"], snapshot["context"]["mapId"])):
            if event.get("event") != name or event.get("reason") != reason or event.get("handle") != handle \
                    or event.get("frame") != snapshot["frame"] or event.get("valueA") != a or event.get("valueB") != b:
                raise ValueError("crash transition native event differs")
            integer(event.get("sequence"), "transition sequence", 1)
            integer(event.get("traceStream"), "transition stream", 1)
            integer(event.get("actorFrame"), "transition actor frame")
        if change["traceStream"] != rebound["traceStream"] or change["sequence"] >= rebound["sequence"] \
                or change["actorFrame"] != rebound["actorFrame"]:
            raise ValueError("crash transition events are reordered or from different boundaries")
        prior_data = self._metadata({"frame":self._last["frame"],"nativeCycle":self._last["nativeCycle"]}, previous)
        if prior_data != proof["samples"][-1]["metadata"] or previous["engineObject"] != proof["samples"][-1]["rawEngine"]:
            raise ValueError("crash transition preceding sample differs")
        if (data["timer"], data["baseX"], data["baseZ"]) != (0, 0, 0) \
                or data["objectPointer"] != proof["objectPointer"] \
                or actor.get("inputOwnership") != 0 or actor.get("reservationId") != 0 \
                or engine.get("pos_y") != proof["height"] \
                or [engine.get("pos_x"), engine.get("pos_z")] != proof["base"] \
                or [engine.get("x"), engine.get("y")] != [terminal["target"]["x"],terminal["target"]["y"]] \
                or engine.get("unk88_y") != 0 or not integer(engine.get("flags"), "transition flags") & 1 \
                or engine["flags"] & 2:
            raise ValueError("crash transition did not restore exact owned pose")
        proof["termination"] = "transition-restored"
        proof["restoredFrame"] = snapshot["frame"]
        proof["transitionRestoration"] = {"snapshot":{k:deepcopy(snapshot[k]) for k in ("frame","nativeCycle","context")},
            "actor":deepcopy(actor),"transition":deepcopy(transition)}
        self._pending = None
        return engine

    def _observe(self, snapshot, actor, previous_actor, transition=None):
        data = self._metadata(snapshot, actor)
        engine = deepcopy(actor["engineObject"])
        if self._pending is not None and transition is not None:
            return self._transition_restore(snapshot, actor, previous_actor, data, engine, transition)
        if not data["timer"] and self._pending is None:
            return engine
        context = {k:snapshot["context"][k] for k in ("mapId", "fieldEpoch", "mapGeneration")}
        if any(context[k] != actor["handle"][k] for k in ("fieldEpoch", "mapGeneration")):
            raise ValueError("crash actor context mismatch")
        if self._pending is None and data["timer"] == 11:
            old = previous_actor
            if old is None or self._last is None or self._last["frame"] != snapshot["frame"]-1 \
                    or self._last["context"] != snapshot["context"]:
                raise ValueError("crash pre-roll lacks the preceding same-context observation")
            prior = self._metadata(
                {"frame":snapshot["frame"]-1,"nativeCycle":old["crashPresentation"]["nativeCycle"]}, old)
            target = actor["target"]
            base = [target["x"]*65536+32768, target["y"]*65536+32768]
            if prior["timer"] != 0 or prior["objectPointer"] != data["objectPointer"] \
                    or old["handle"] != actor["handle"] \
                    or actor["motionPhase"] != "IDLE" or actor["motionKind"] != "NONE" \
                    or actor["motionElapsed"] != actor["motionDuration"] \
                    or actor["logical"] != actor["target"] \
                    or actor["inputOwnership"] != 0 or actor["reservationId"] != 0 \
                    or [data["baseX"],data["baseZ"]] != base \
                    or [engine["pos_x"],engine["pos_z"]] != base \
                    or any(old[k] != actor[k] for k in ("origin", "target", "logical", "motionDuration",
                        "commitSequence", "authorityGeneration", "engineAnchorGeneration",
                        "presentationGeneration")):
                raise ValueError("crash pre-roll did not preserve the settled base pose")
            self._preroll_previous = deepcopy(old)
            return engine
        if self._pending is None:
            old = previous_actor
            if self._last is None or self._last["frame"] != snapshot["frame"]-1 \
                    or self._last["context"] != snapshot["context"]:
                raise ValueError("crash start lacks the preceding same-context observation")
            prior = old["crashPresentation"]
            prior_snapshot = {"frame":snapshot["frame"]-1,"nativeCycle":prior["nativeCycle"]}
            self._metadata(prior_snapshot, old)
            walk_terminal = old["motionPhase"] == "MOVING" and old["motionKind"] == "WALK" \
                and old["motionElapsed"] == actor["motionDuration"]-1 \
                and actor["commitSequence"] == (old["commitSequence"]+1) & 0xFFFFFFFF \
                and actor["logical"] == actor["target"]
            idle_blocked = old["motionPhase"] == "IDLE" and old["motionKind"] == "NONE" \
                and old["motionElapsed"] == old["motionDuration"] \
                and old["commitSequence"] == actor["commitSequence"] \
                and old["logical"] == actor["logical"] == actor["target"] \
                and old["inputOwnership"] == actor["inputOwnership"] == 0 \
                and old["reservationId"] == actor["reservationId"] == 0
            preroll = prior["timer"] == 11
            if data["timer"] != 10 or prior["timer"] not in (0, 11) \
                    or prior["objectPointer"] != data["objectPointer"] or old["handle"] != actor["handle"] \
                    or actor["motionPhase"] != "IDLE" or actor["motionKind"] != "NONE" \
                    or actor["motionElapsed"] != actor["motionDuration"] \
                    or not (walk_terminal or idle_blocked) \
                    or any(old[k] != actor[k] for k in ("origin", "target", "motionDuration",
                        "authorityGeneration", "engineAnchorGeneration", "presentationGeneration")):
                raise ValueError("crash did not begin at a settled Walk or blocked-idle boundary")
            if len(self.proofs) >= self.max_proofs:
                raise ValueError("crash proof bound exceeded")
            target = actor["target"]
            base = [target["x"]*65536+32768, target["y"]*65536+32768]
            if [data["baseX"],data["baseZ"]] != base:
                raise ValueError("crash base is not the exact target")
            if preroll and ([prior["baseX"],prior["baseZ"]] != base
                    or [old["engineObject"]["pos_x"],old["engineObject"]["pos_z"]] != base):
                raise ValueError("crash pre-roll did not preserve the exact base pose")
            proof = {"startFrame":snapshot["frame"],"handle":deepcopy(actor["handle"]),
                "context":context,"objectPointer":data["objectPointer"],"base":base,
                "startBoundary":"walk-terminal" if walk_terminal else "blocked-idle",
                "preRollFrame":snapshot["frame"]-1 if preroll else None,
                "preRollPreviousActor":deepcopy(self._preroll_previous) if preroll else None,
                "height":old["engineObject"]["pos_y"],"terminal":deepcopy(actor),
                "previousActor":deepcopy(old),"samples":[],"restoredFrame":None}
            self.proofs.append(proof)
            self._pending = proof
            self._preroll_previous = None
        proof = self._pending
        terminal = proof["terminal"]
        n = len(proof["samples"])
        if snapshot["frame"] != proof["startFrame"]+n or data["timer"] != 10-n \
                or context != proof["context"] or data["objectPointer"] != proof["objectPointer"] \
                or data["handle"] != proof["handle"] or [data["baseX"],data["baseZ"]] != proof["base"] \
                or any(actor[k] != terminal[k] for k in ("motionPhase", "motionKind", "motionElapsed",
                    "motionDuration", "origin", "target", "commitSequence", "authorityGeneration",
                    "engineAnchorGeneration", "presentationGeneration")):
            raise ValueError("crash countdown, owner or terminal changed")
        if actor["logical"] != actor["target"] or actor["inputOwnership"] != 0 or actor["reservationId"] != 0:
            raise ValueError("crash lacks settled logical ownership")
        flags = integer(engine["flags"], "engine flags")
        offset = OFFSETS[data["timer"]]
        if not flags & 1 or flags & 2 or engine["unk88_y"] != 0 \
                or [engine["x"],engine["y"]] != [actor["target"]["x"],actor["target"]["y"]] \
                or engine["pos_x"] != proof["base"][0]+offset \
                or engine["pos_z"] != proof["base"][1]-offset or engine["pos_y"] != proof["height"]:
            raise ValueError("crash raw pose differs from exact owned offset")
        proof["samples"].append({"frame":snapshot["frame"],"nativeCycle":snapshot["nativeCycle"],
            "metadata":deepcopy(data),"rawEngine":deepcopy(engine),"offset":offset})
        if data["timer"]:
            engine["pos_x"],engine["pos_z"] = proof["base"]
        else:
            proof["restoredFrame"] = snapshot["frame"]
            proof["termination"] = "countdown-restored"
            self._pending = None
        return engine
