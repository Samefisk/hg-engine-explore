"""Controller-owned mounted pacing rows and copied-data failure controls."""
from copy import deepcopy

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_mount_pacing_measurement import check_pair_pose, MAIN_DURATIONS
from tools.overworld.normal_play_observer import complete_travel

KIND = "mounted-frame-pacing-v1"
REQUIREMENT = "legacy.mounted-smoothness"
RULES = (("natural-input", "held-input-tile-distance", 7, "eq"),
    ("live-actor-identity", "mounted-smoothness-cyndaquil-identity", [1,"MOUNTED",155,1], "eq"),
    ("rendered-motion", "rendered-motion-count", 7, "eq"),
    ("rendered-motion", "pair-delta-mismatch-count", 0, "eq"),
    ("frame-pacing", "maximum-callback-gap", 2, "lte"),
    ("frame-pacing", "maximum-boundary-gap", 2, "lte"),
    ("frame-pacing", "maximum-leading-zero-frames", 1, "lte"),
    ("engine-boundary", "normal-player-step-callback-count", 7, "eq"),
    ("control-release", "recovery-terminal-state", [1,0,1], "eq"))
CLAIMS = tuple(dict.fromkeys(r[0] for r in RULES))
MEANINGS = {"mounted-pacing-missing-start":"MOTION_STARTED", "mounted-pacing-missing-commit":"LOGICAL_COMMIT",
            "mounted-pacing-missing-finish":"MOTION_FINISHED", "mounted-pacing-missing-return":"CONTROL_RETURNED"}
FAULTS = ("mounted-pacing-absent-subject", "mounted-pacing-stale-subject", "mounted-pacing-bad-pair",
          "mounted-pacing-bad-completed-pair", "mounted-pacing-missing-reader", *MEANINGS)


def contract():
    result = {}
    for claim, name, expected, operator in RULES:
        result.setdefault(claim, []).append(dict(name=name, expected=deepcopy(expected), operator=operator,
            type="array" if isinstance(expected,list) else "integer", validator="meaningful-observation"))
    return result


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    if replay.get("passed") is not True or replay.get("failures") != [] or meter.get("passed") is not True \
            or meter.get("ready") is not True or meter.get("closed") is not True \
            or meter.get("acceptedProof") is not False or meter.get("failures") != []:
        raise ValueError("mounted pacing lacks closed independent replay")
    if record.get("sessionCleanup") != dict(sessionId=record.get("sessionId"),closed=True,errors=[]):
        raise ValueError("mounted pacing private session did not close cleanly")
    subject, initial = meter.get("subject"), meter.get("initial")
    bound = select_current_actor(initial, subject)
    actor = next(a for a in initial["actors"] if a["handle"] == bound["handle"])
    identity = [int(actor.get("identityVerified") is True),actor.get("role"),actor.get("species"),actor.get("inputOwnership")]
    if identity != [1,"MOUNTED",155,1]: raise ValueError("mounted pacing lacks live Cyndaquil")
    cleanup = meter.get("cleanup", {})
    reader = cleanup.get("mountPacing", {})
    if cleanup.get("closed") is not True or cleanup.get("advancedFrames") != 0 \
            or cleanup.get("acceptedProof") is not False or reader.get("closed") is not True \
            or reader.get("failure") is not None or reader.get("subject") != subject:
        raise ValueError("mounted pacing reader cleanup differs")
    windows = meter.get("windows", [])
    if len(windows) != 2: raise ValueError("mounted pacing needs separate recovery")
    if tuple(m.get("duration") for m in windows[0].get("motions", [])) != MAIN_DURATIONS:
        raise ValueError("mounted Cyndaquil acceleration duration differs")
    callback_total = step_total = 0
    for window, expected in zip(windows,(7,1)):
        motions, callbacks, steps, traces = (window.get(k,[]) for k in ("motions","callbacks","steps","traces"))
        if len(motions) != expected or len(steps) != expected or not callbacks:
            raise ValueError("mounted pacing missing complete motion or callback")
        for name in MEANINGS.values():
            if sum(e.get("data",{}).get("event") == name for e in traces) != expected:
                raise ValueError("mounted pacing missing native " + name)
        for motion in motions:
            if not complete_travel(motion) or motion.get("kind") != "WALK" \
                    or motion.get("target") != [motion["origin"][0]+1,motion["origin"][1]] \
                    or motion.get("commitAfter") != (motion["commitBefore"]+1)&0xFFFFFFFF:
                raise ValueError("mounted pacing incomplete Right Walk")
        for event in callbacks + steps:
            value = event["data"]
            if value.get("subject") != subject or value.get("publicSubject",{}).get("handle") != actor["handle"]:
                raise ValueError("mounted pacing callback owner differs")
            check_pair_pose(value)
        callback_total += len(callbacks)
        step_total += len(steps)
    if reader.get("counts") != dict(presentation=callback_total,playerStep=step_total):
        raise ValueError("mounted pacing callback totals differ")
    main = windows[0]
    callbacks, motions = main["callbacks"], main["motions"]
    cycles = [e["data"]["returnNativeCycle"] for e in callbacks]
    if any(type(c) is not int for c in cycles) or any(b<a for a,b in zip(cycles,cycles[1:])):
        raise ValueError("mounted pacing callback clock differs")
    callback_gap = max((b-a for a,b in zip(cycles,cycles[1:])),default=0)
    boundary_gap = 0
    for previous,motion in zip(motions,motions[1:]):
        lifecycle = main["traces"]
        start = [e["data"] for e in lifecycle if e["frame"] == motion["startFrame"]
                 and e["data"].get("event") == "MOTION_STARTED"]
        finish = [e["data"] for e in lifecycle if e["frame"] == motion["finishFrame"]
                  and e["data"].get("event") == "MOTION_FINISHED"]
        if len(start) != 1 or len(finish) != 1:
            raise ValueError("mounted pacing missing boundary lifecycle")
        ends = [e for e in callbacks if e["data"]["publicSubject"].get("target") == dict(zip(("x","y"),previous["target"]))
                and e["data"]["publicSubject"].get("motionElapsed") == previous["duration"]]
        starts = [e for e in callbacks if e["data"]["publicSubject"].get("origin") == dict(zip(("x","y"),motion["origin"]))
                  and start[0]["actorFrame"] <= e["data"]["returnActorFrame"] <= finish[0]["actorFrame"]]
        if not ends or not starts: raise ValueError("mounted pacing missing boundary pose")
        gap = starts[0]["data"]["returnNativeCycle"]-ends[-1]["data"]["returnNativeCycle"]
        if gap < 0: raise ValueError("mounted pacing reversed boundary clock")
        boundary_gap = max(boundary_gap,gap)
    leading = max(sum(s["elapsed"]==0 for s in m["samples"]) for m in motions)
    control = reader.get("latestCompletedPose",{}).get("avatarControl",{})
    if type(control.get("flags")) is not int: raise ValueError("mounted pacing missing recovery control")
    recovery = [int(len(windows[1]["motions"])==1),control["flags"]&1,int(control.get("playerMoveState") in (0,3))]
    distance = motions[-1]["target"][0]-motions[0]["origin"][0]
    values = [distance,identity,len(motions),0,callback_gap,boundary_gap,leading,len(main["steps"]),recovery]
    result = []
    for (claim,name,expected,operator),value in zip(RULES,values):
        if not (value == expected if operator == "eq" else type(value) is int and value <= expected):
            raise ValueError("mounted pacing failed " + name)
        result.append(dict(claim=claim,name=name,value=value,expected=deepcopy(expected),operator=operator,passed=True))
    return result


class MountedPacingNegative:
    def __init__(self,fault):
        if fault not in FAULTS: raise ValueError("unknown mounted pacing fault")
        self.fault,self.applied = fault,False

    def mutate(self,row,subjects):
        if self.applied or row.get("phase") != "observe" or not subjects: return row
        changed = deepcopy(row)
        handles = {s["handle"]["value"] for s in subjects.values()}
        for sample in changed.get("samples",[]):
            actor = next((a for a in sample.get("actors",[]) if a.get("handle",{}).get("value") in handles),None)
            if actor is not None and self.fault == "mounted-pacing-absent-subject":
                sample["actors"].remove(actor); self.applied=True
            elif actor is not None and self.fault == "mounted-pacing-stale-subject":
                actor["authorityGeneration"]+=1; self.applied=True
            elif self.fault == "mounted-pacing-missing-reader" and "mountPacing" in sample:
                sample.pop("mountPacing"); self.applied=True
            elif self.fault == "mounted-pacing-bad-completed-pair" and sample.get("mountPacing",{}).get("latestCompletedPose"):
                sample["mountPacing"]["latestCompletedPose"]["mount"]["pos_x"]+=1; self.applied=True
            if self.applied: break
        if not self.applied:
            for event in changed.get("events",[]):
                data=event.get("data",{})
                if self.fault in MEANINGS and data.get("actorHandle") in handles and data.get("event") == MEANINGS[self.fault]:
                    data["event"]="WORLD_EFFECT"; self.applied=True
                elif self.fault == "mounted-pacing-bad-pair" and data.get("observation") == "mount-pacing-presentation":
                    data["mount"]["pos_x"]+=1; self.applied=True
                if self.applied: break
        return changed if self.applied else row


def validate_negative_result(result,fault):
    if fault not in FAULTS or result.get("passed") is not False:
        raise ValueError("mounted pacing copied control did not fail")
    failures=result.get("failures",[])+result.get("measurements",{}).get(KIND,{}).get("failures",[])
    reasons=set()
    for value in failures:
        if isinstance(value,str): reasons.add(value)
        elif isinstance(value,dict): reasons.update(value.get(k) for k in ("detail","message") if isinstance(value.get(k),str))
    expected = ("missing native "+MEANINGS[fault]) if fault in MEANINGS else {
        "mounted-pacing-absent-subject":"selected handle must name exactly one current active actor",
        "mounted-pacing-stale-subject":"selected actor has a stale authorityGeneration",
        "mounted-pacing-bad-pair":"mounted base, facing or rider offset differs",
        "mounted-pacing-bad-completed-pair":"mounted base, facing or rider offset differs",
        "mounted-pacing-missing-reader":"'mountPacing'"}[fault]
    if expected not in reasons: raise ValueError("mounted pacing copied control failed for an unrelated reason: "+fault)
