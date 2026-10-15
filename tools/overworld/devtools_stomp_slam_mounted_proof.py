"""Mounted-body case of the one shared native Slam/contact meter."""
from copy import deepcopy
from tools.overworld import devtools_stomp_slam_proof as shared
from tools.overworld.devtools_stomp_slam_measurement import MOUNTED_KIND as KIND, MOUNTED_REQUIREMENT as REQUIREMENT, need

CLAIMS = shared.CLAIMS
FAULTS = tuple(f for f in shared.FAULTS if f != "damage-receipt") + (
    "mount-damage-receipt", "mount-input-owner", "stale-mount", "unforced-jump", "missing-mount-release")
NAMES = dict(shared.NAMES, **{
    "live-actor-identity": "same-current-wild-snorlax-and-attached-passive-mount",
    "collision-decision": "physical-sweep-at-speed16-accepts-one-mount-hit20",
    "control-release": "one-slam-commit-shared-mounted-jump2-and-exact-seat-heights"})


def contract():
    return {claim:[dict(name=NAMES[claim],operator="eq",type="integer",
                       validator="meaningful-observation",expected=1)] for claim in CLAIMS}


def measurements(replay, record):
    result = replay.get("measurements", {}).get(KIND, {})
    need(result.get("kind") == KIND and result.get("passiveRole") == "MOUNTED"
         and result.get("requirements") == [REQUIREMENT]
         and result.get("subjects", {}).get("passive", {}).get("role") == "MOUNTED",
         "mounted Slam proof has another fixture role")
    baseline, terminal = result.get("mountedBaseline"), result.get("mountedTerminal")
    before, hit, after = (result.get(key,{}) for key in ("beforeMountHP","contactMountHP","afterMountHP"))
    player = [result.get(key,{}) for key in ("beforeHP","contactHP","afterHP")]
    jump, release = result.get("mountedJump",{}), result.get("mountedJumpRelease",{})
    need(isinstance(baseline,dict) and isinstance(terminal,dict)
         and all(baseline.get(k) == terminal.get(k) for k in ("pos_y","face_y","unk88_y"))
         and result.get("contact",{}).get("recipientRole") == "MOUNTED"
         and before.get("hp",0)-hit.get("hp",0) == 20 and hit.get("lastDamage") == 20
         and hit.get("hitCount") == before.get("hitCount",0)+1
         and after.get("hp") == hit.get("hp") and after.get("hitCount") == hit.get("hitCount")
         and all(p.get("hp") == player[0].get("hp") and p.get("acceptedHits") == player[0].get("acceptedHits") for p in player)
         and jump.get("actor") == result["subjects"]["passive"]["handle"]
         and (jump.get("plan",{}).get("flags"),jump.get("plan",{}).get("distance"),jump.get("plan",{}).get("duration")) == (1,2,18)
         and [s["elapsed"] for s in jump.get("samples",[])] == list(range(jump.get("startElapsed",-1),19))
         and release.get("actor") == jump.get("actor")
         and [e["event"] for e in release.get("events",[])] == ["LOGICAL_COMMIT","MOTION_FINISHED","CONTROL_RETURNED"],
         "mounted Slam lacks real mount hit20, one shared forced Jump2 or restored seat")
    # Reuse the same Slam arc/notice/release claim validation. The separate
    # mount receipt is mapped only inside this adapter; Player HP stays intact.
    copied = deepcopy(replay)
    old = copied["measurements"][shared.KIND] = deepcopy(result)
    old["requirements"] = [shared.REQUIREMENT]
    for key,mount_hp in zip(("beforeHP","contactHP","afterHP"),(before,hit,after)):
        old[key] = dict(mount_hp,acceptedHits=mount_hp["hitCount"])
    values = shared.measurements(copied, record)
    for value in values:value["name"] = NAMES[value["claim"]]
    return values


class StompSlamMountedNegative:
    def __init__(self, fault):
        need(fault in FAULTS,"unknown copied mounted Slam control")
        self.fault,self.applied = fault,False
        self.shared = shared.StompSlamNegative(fault) if fault in shared.FAULTS else None

    def mutate(self,row,subjects):
        if self.shared:
            value=self.shared.mutate(row,subjects)
            self.applied=self.shared.applied
            return value
        value=deepcopy(row)
        samples=value.get("samples",[]) + ([value["snapshot"]] if "snapshot" in value else [])
        for sample in samples:
            if value.get("phase") != "observe" or self.applied:continue
            passive=next(a for a in sample["actors"] if a.get("role")=="MOUNTED")
            if self.fault=="mount-input-owner":passive["inputOwnership"]=0
            elif self.fault=="stale-mount":passive["handle"]["encounterGeneration"]+=1
            elif self.fault=="mount-damage-receipt":
                target=next(t for t in sample["pokemonCombat"]["targets"] if t.get("role")=="MOUNTED")
                if target["hitCount"]==0:continue
                target["hitCount"]-=1
            elif self.fault=="unforced-jump":
                from tools.overworld.devtools_walk_matrix_observer import decode_motion
                target=next(t for t in sample["pokemonCombat"]["targets"] if t.get("role")=="MOUNTED")
                if passive["motionKind"]!="HOP":continue
                raw=bytearray.fromhex(target["motion"]["rawHex"]);raw[37]=0
                target["motion"]=decode_motion(bytes(raw))
            else:
                events=value.get("events",[])
                target=next((e for e in events if e.get("data",{}).get("actorHandle")==passive["handle"]["value"]
                             and e["data"].get("event")=="CONTROL_RETURNED"),None)
                if target is None:continue
                events.remove(target)
            self.applied=True
        return value


def validate_negative_result(result,fault):
    if fault in ("wrong-knockback","wrong-distance"):
        reason="shared anchor or rider height"
    elif fault in shared.FAULTS:return shared.validate_negative_result(result,fault)
    else:
        reason={"mount-input-owner":"passive mount lost current input ownership",
                "stale-mount":"exactly one current active actor",
                "mount-damage-receipt":"exactly one normal20 hit",
                "unforced-jump":"queued forced Jump2",
                "missing-mount-release":"ordered commit/finish/input return"}[fault]
    need(result.get("passed") is False and any(reason in str(f) for f in result.get("failures",[])),
         "copied mounted Slam control did not reject its exact owner/contact fault")
