"""Route-only copied-data controls. No live input or observation mutation."""
from copy import deepcopy

MEANINGS = {"route-missing-start":"MOTION_STARTED", "route-missing-commit":"LOGICAL_COMMIT",
            "route-missing-finish":"MOTION_FINISHED", "route-missing-return":"CONTROL_RETURNED"}
FAULTS = ("absent-subject", "stale-subject", *MEANINGS,
          "route-missing-cpu", "route-missing-pin", "route-missing-cleanup")


def validate_negative_result(fault, result):
    """Only this mutation's own rejection proves its negative control."""
    if fault not in FAULTS or not isinstance(result,dict) or result.get("passed") is not False:
        raise ValueError("route negative control did not fail")
    if fault=="route-missing-cleanup":
        if not isinstance(result.get("failures"),list):
            raise ValueError("route negative control lacks failures")
        valid=any(error.get("code")=="route-control-cleanup-rejected"
                  and error.get("message")=="player fault cleanup must close the core"
                  for error in result.get("failures",[]) if isinstance(error,dict))
    else:
        measurements=result.get("measurements")
        if not isinstance(measurements,dict) or not isinstance(measurements.get("live-route-control-v1"),dict):
            raise ValueError("route negative control lacks its measurement")
        failures=measurements["live-route-control-v1"].get("failures")
        if not isinstance(failures,list):
            raise ValueError("route negative control lacks measurement failures")
        if fault in MEANINGS:
            key={"route-missing-start":"start","route-missing-commit":"commit",
                 "route-missing-finish":"finish","route-missing-return":"control"}[fault]
            expected={name:0 if name==key else 1 for name in ("start","commit","finish","control")}
            valid=any(error.get("code")=="follower-terminal-trace-gap" and error.get("detail")==expected
                      and all(type(value) is int for value in error["detail"].values())
                      for error in failures if isinstance(error,dict))
        else:
            expected={"absent-subject":"exact follower is absent or duplicated",
                      "stale-subject":"selected actor belongs to a stale fieldEpoch",
                      "route-missing-cpu":"CPU work receipt is not one measured cycle",
                      "route-missing-pin":"player pin sequence differs"}[fault]
            valid=any(error.get("code")=="cadence-observation-invalid" and error.get("detail")==expected
                      for error in failures if isinstance(error,dict))
    if not valid:
        raise ValueError("route negative control failed for another reason: "+fault)
    return True


class RouteControlNegative:
    def __init__(self, fault):
        if fault not in FAULTS:
            raise ValueError("unknown route-control copied-data fault")
        self.fault, self.applied = fault, False

    def mutate(self, row, subjects):
        if self.applied or not isinstance(row,dict):
            return row
        values = subjects.values() if isinstance(subjects,dict) else subjects
        selected = [s for s in values if isinstance(s,dict) and s.get("species")==155 and s.get("role")=="FOLLOWER"]
        if len(selected)!=1:
            return row
        subject=selected[0]
        def changed():
            self.applied=True
            return deepcopy(row)
        if self.fault=="route-missing-cleanup":
            if row.get("command")!="route-control.close" or row.get("phase")!="cleanup":return row
            receipts=row.get("receipt",{}).get("routeControl",{}).get("receipts",[])
            for index,receipt in enumerate(receipts):
                if receipt.get("action")=="closed" and receipt.get("requiresCoreClose") is True:
                    result=changed()
                    result["receipt"]["routeControl"]["receipts"][index]["requiresCoreClose"]=False
                    return result
            return row
        if row.get("phase")!="observe" or not isinstance(row.get("samples"),list):
            return row
        if self.fault in ("absent-subject","stale-subject"):
            for index,sample in enumerate(row["samples"]):
                if sample.get("routeControl") is not None:continue
                for slot,actor in enumerate(sample.get("actors",[])):
                    if actor.get("active") is True and actor.get("handle")==subject.get("handle"):
                        result=changed(); actors=result["samples"][index]["actors"]
                        if self.fault=="absent-subject":actors.pop(slot)
                        else:actors[slot]["handle"]["fieldEpoch"]=(actors[slot]["handle"]["fieldEpoch"]%65535)+1
                        return result
        elif self.fault in MEANINGS:
            baseline_frames={s["frame"] for s in row["samples"] if s.get("routeControl") is None}
            for index,event in enumerate(row.get("events",[])):
                data=event.get("data",{})
                handle={"value":data.get("actorHandle"),**data.get("actor",{})}
                if event.get("kind")=="native" and event.get("frame") in baseline_frames \
                        and handle==subject.get("handle") and data.get("event")==MEANINGS[self.fault]:
                    result=changed();result["events"][index]["data"]["event"]="WORLD_EFFECT"
                    return result
        else:
            action="cpu-work" if self.fault=="route-missing-cpu" else "player-pinned"
            for index,sample in enumerate(row["samples"]):
                for receipt_index,receipt in enumerate((sample.get("routeControl") or {}).get("receipts",[])):
                    if receipt.get("action")!=action:continue
                    result=changed()
                    target=result["samples"][index]["routeControl"]["receipts"][receipt_index]
                    if action=="cpu-work":target["workCpuNs"]+=1
                    else:target["after"][0]+=1
                    return result
        return row
