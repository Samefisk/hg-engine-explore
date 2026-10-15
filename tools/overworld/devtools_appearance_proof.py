"""Exact palette acceptance and copied-fault controls; no emulator control."""
from copy import deepcopy
from tools.overworld.devtools_appearance_measurement import CONFIG, DAMAGE, COOLDOWN, AMBUSH_COOLDOWN, KINDS, RAM, AMBUSH

_NAMES = {
    DAMAGE: {
        "live-actor-identity": ("current-wild-mount-and-healed-follower",),
        "profile-resolution": ("ordinary-sealed-ambush-collision-profile",),
        "engine-boundary": ("two-real-party-hp-hits-and-one-wild-hit", "same-party-native-nurse-heal"),
        "rendered-motion": ("exact-two-red-strength-sdk-bytes-and-mat-use", "real-wild-red-sdk-bytes-and-mat-use",
                            "same-hp-actor-clock-pulse-reuses-private-palette"),
        "natural-input": ("ordinary-collisions-and-stock-nurse-input",),
        "control-release": ("full-hp-follower-original-palette-and-no-tint-callback",),
    },
    COOLDOWN: {
        "live-actor-identity": ("current-full-hp-onix",),
        "profile-resolution": ("all-current-own-ram-conditions",),
        "engine-boundary": ("every-prepared-condition-in-native-cooldown",),
        "rendered-motion": ("exact-blue-sdk-bytes-and-mat-use",),
        "natural-input": ("real-ram-crash-with-no-timer-or-mask-writes",),
        "control-release": ("natural-deadline-clears-tint-record-and-callback",),
    },
}
_NAMES[AMBUSH_COOLDOWN] = deepcopy(_NAMES[COOLDOWN])
_NAMES[AMBUSH_COOLDOWN]["live-actor-identity"] = ("current-full-hp-weepinbell",)
_NAMES[AMBUSH_COOLDOWN]["profile-resolution"] = ("all-current-own-ambush-conditions",)
_NAMES[AMBUSH_COOLDOWN]["natural-input"] = ("real-timed-ambush-ends-with-no-timer-or-mask-writes",)
_COMMON = ("palette-missing-reader", "palette-stale-owner", "palette-wrong-rgb", "palette-missing-sdk",
           "palette-incomplete-sdk", "palette-wrong-mat", "palette-wrong-strength")
_EXTRA = {DAMAGE:("palette-party-hp-shadow", "palette-fake-heal", "palette-full-hp-still-tinted", "palette-wrong-pulse-clock"),
          COOLDOWN:("palette-omitted-condition", "palette-active-condition", "palette-expired-condition", "palette-mask-disabled")}

_EXTRA[AMBUSH_COOLDOWN] = _EXTRA[COOLDOWN]

def requirement(kind): return CONFIG[kind]["requirement"]
def claims(kind): return tuple(_NAMES[kind])
def faults(kind): return _COMMON + _EXTRA[kind]
def contract(kind):
    return {claim:[dict(name=name,operator="eq",type="integer",validator="meaningful-observation",expected=1)
                   for name in names] for claim,names in _NAMES[kind].items()}


def measurements(kind, replay, record):
    meter=replay.get("measurements",{}).get(kind,{})
    if (replay.get("passed") is not True or replay.get("failures") != []
            or meter.get("ready") is not True or meter.get("passed") is not True
            or meter.get("acceptedProof") is not False
            or meter.get("observedFrames",0) < CONFIG[kind]["minimum"]
            or meter.get("observedFrames") != replay.get("observedFrames")
            or set(meter.get("subjects",{})) != {s[0] for s in CONFIG[kind]["subjects"]}):
        raise ValueError("Pokémon palette lacks completed exact native replay")
    if kind == DAMAGE:
        if (len(meter.get("hits",{}).get("cyndaquil",[])) < 2
                or not meter.get("hits",{}).get("snorlax")
                or len({p["strength"] for p in meter.get("palettes",{}).get("cyndaquil",[])}) < 2
                or len({p["hitCount"] for p in meter.get("palettes",{}).get("cyndaquil",[])}) < 2
                or meter.get("pulseDirections",{}).get("cyndaquil") != [-1,1]
                or not meter.get("palettes",{}).get("snorlax")
                or not meter.get("naturalHeal") or not meter.get("cleared")
                or meter.get("attackFrames",0) < 1):
            raise ValueError("red palette lacks real distinct hits, material use, native healing and full-HP clear")
    elif kind == AMBUSH_COOLDOWN:
        if (not meter.get("blue") or not meter.get("expired") or not meter.get("firstCooldown")
                or {s["application"] for s in meter.get("blueConditions",{}).get("states",[])} != {AMBUSH}):
            raise ValueError("Ambush blue lacks all native cooldowns, upload/material use and natural expiry")
    elif (not meter.get("blue") or not meter.get("expired") or not meter.get("crashes")
            or {s["application"] for s in meter.get("blueConditions",{}).get("states",[])} != {RAM}):
        raise ValueError("blue palette lacks all native cooldowns, real upload/material use and natural expiry")
    if record.get("sessionCleanup") != dict(sessionId=record.get("sessionId"),closed=True,errors=[]):
        raise ValueError("Pokémon palette private session did not close")
    return [dict(claim=claim,name=name,value=1,operator="eq",expected=1,passed=True)
            for claim,names in _NAMES[kind].items() for name in names]


class AppearanceNegative:
    def __init__(self, kind, fault):
        if kind not in KINDS or fault not in faults(kind):
            raise ValueError("unknown Pokémon palette copied-data control")
        self.kind,self.fault,self.applied=kind,fault,False

    def mutate(self,row,subjects):
        if row.get("phase") != "observe": return row
        changed=deepcopy(row)
        samples=list(changed.get("samples",[]))
        if isinstance(changed.get("snapshot"),dict):samples.append(changed["snapshot"])
        for sample in samples:
            if self.fault == "palette-wrong-pulse-clock" and "actorFrame" in sample:
                sample["actorFrame"]=(sample["actorFrame"]+32)&0xffffffff;self.applied=True
            data=sample.get("pokemonAppearance",{})
            if self.fault == "palette-missing-reader" and data:
                sample.pop("pokemonAppearance");self.applied=True
            for view in data.get("records",[]):
                if self.fault == "palette-stale-owner":view["handle"]["mapGeneration"]+=1;self.applied=True
                elif self.fault == "palette-wrong-rgb":view["tintedHex"]=view["originalHex"];self.applied=True
                elif self.fault == "palette-wrong-strength":view["strength"]=16;self.applied=True
            for upload in data.get("uploads",{}).values():
                if self.fault == "palette-incomplete-sdk":upload["completed"]=False;self.applied=True
            for material in data.get("materials",{}).values():
                if self.fault == "palette-wrong-mat":material["afterWord"]=material["beforeWord"];self.applied=True
            for conditions in data.get("conditions",{}).values():
                states=conditions.get("states",[])
                application=AMBUSH if self.kind==AMBUSH_COOLDOWN else RAM
                condition=next((s for s in states if s["application"]==application),None)
                if self.fault == "palette-omitted-condition" and condition:
                    conditions["states"]=[s for s in states if s["application"]!=application];self.applied=True
                elif self.fault == "palette-active-condition" and condition:
                    condition["flags"]|=1;self.applied=True
                elif self.fault == "palette-expired-condition" and condition:
                    condition["cooldownUntil"]=conditions["frame"];self.applied=True
                elif self.fault == "palette-mask-disabled" and states:
                    for s in states:s["enabled"]=False
                    conditions["enabledMask"]=0;self.applied=True
            if self.fault == "palette-party-hp-shadow":
                for target in sample.get("pokemonCombat",{}).get("targets",[]):
                    if target.get("species")==155 and target.get("hitCount",0):
                        for mon in sample.get("party",[]):
                            if mon["personality"]==target["personality"]:mon["hp"]=mon["maxHp"];self.applied=True
            if self.fault == "palette-full-hp-still-tinted":
                for clear in data.get("clears",{}).values():
                    clear["draw"]["drawCommand"]=4;self.applied=True
        events=changed.get("events",[])
        if self.fault == "palette-missing-sdk":
            kept=[e for e in events if e.get("data",{}).get("observation")!="appearance-sdk-upload-complete"]
            self.applied |= len(kept)!=len(events);changed["events"]=kept
        elif self.fault == "palette-fake-heal":
            for event in events:
                if event.get("data",{}).get("observation")=="appearance-native-heal":
                    event["data"]["synthetic"]=True;self.applied=True
        return changed


def validate_negative_result(kind, result, fault):
    if fault not in faults(kind) or result.get("passed") is not False or not result.get("failures"):
        raise ValueError("Pokémon palette control did not reject "+fault)
    return True
