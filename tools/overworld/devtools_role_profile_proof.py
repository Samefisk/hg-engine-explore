"""Prepared follower-to-mounted Owner byte transfer, not input/motion proof."""
from copy import deepcopy
import struct

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_runtime import actor_identity_checks
from tools.overworld.devtools_resolver_parity import raw_hex

WITNESS = dict(species=56, subjectIdentity=2920357538, form=0, level=3)
PARTY_SLOT = 2


def require(ok, reason):
    if not ok:
        raise ValueError("role transfer: " + reason)


def number(value, low=0, high=0xFFFFFFFF):
    require(type(value) is int and low <= value <= high, "invalid integer")
    return value


def _actor(snapshot, role):
    require(snapshot.get("fieldAvailable") is True
            and snapshot.get("observationBoundary") == "main-task-queue-completion", "incoherent endpoint")
    matches = [a for a in snapshot["actors"] if a.get("role") == role
               and all(a.get(k) == v for k,v in WITNESS.items())]
    require(len(matches) == 1, "wrong saved " + role + " subject")
    actor = matches[0]
    select_current_actor(snapshot, actor)
    require(actor["handle"]["slot"] == 7, "wrong follower actor slot")
    mon = snapshot["party"][PARTY_SLOT]
    require(mon.get("identityVerified") is True and mon.get("slot") == PARTY_SLOT
            and mon.get("personality") == WITNESS["subjectIdentity"]
            and all(mon.get(k) == WITNESS[k] for k in ("species","form","level"))
            and mon.get("isEgg") is False and number(mon.get("hp"),1,65535)>0,
            "wrong eligible saved party owner")
    require(snapshot["selector"]["activeFollowerPartySlot"] == PARTY_SLOT, "active party slot differs")
    return actor


def inspect_transfer(events, initial, final, *, allow_reader_control=False):
    """Validate <=128 framed profileObservation events and both real endpoints.

    The parent authenticates ROM/code, retained raw records and session cleanup.
    This does not prove normal Select input, a Hop, or resolver provenance.
    """
    try:
        require(type(allow_reader_control) is bool, "invalid reader control option")
        has_control = any("readerControl" in e.get("data", {}) for e in events)
        require(allow_reader_control or not has_control, "reader control is not ordinary transfer proof")
        if has_control:
            inspect_reader_control(events)
        return _inspect(events, initial, final)
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise ValueError("role transfer: missing or malformed evidence") from error


def inspect_reader_control(events):
    """Validate one native-memory calibration receipt, not ordinary transfer."""
    try:
        require(isinstance(events,list) and 1 <= len(events) <= 128, "missing bounded calibration events")
        controls=[e for e in events if "readerControl" in e.get("data",{})]
        mounts=[e for e in events if e.get("data",{}).get("observation")=="role-profile-mount"]
        require(len(controls)==len(mounts)==1 and controls[0] is mounts[0], "unique mount reader control missing")
        event=controls[0];mount=event["data"];c=mount["readerControl"]
        require(event["kind"]=="native-observation" and mount["setupMode"]=="prepared"
                and type(mount["returnValue"]) is int and mount["returnValue"]==1, "calibration mount failed")
        require(c["acceptedProof"] is False and c["guestAdvanced"] is False and c["rejected"] is True
                and type(c["writes"]) is int and c["writes"]==2, "calibration flags/writes differ")
        require(c["reason"]=="role profile: mounted Owner snapshot differs from Begin inputs", "wrong calibration rejection")
        before=raw_hex(c["beforeSnapshotHex"],104)
        fault=raw_hex(c["faultSnapshotHex"],104)
        restored=raw_hex(c["restoredSnapshotHex"],104)
        expected=bytearray(before);expected[8]^=1
        require(fault==bytes(expected) and restored==before, "calibration bytes/restoration differ")
        require(raw_hex(c["beforeHex"],1)==before[8:9] and raw_hex(c["faultHex"],1)==fault[8:9]
                and raw_hex(c["restoredHex"],1)==before[8:9], "calibration byte receipt differs")
        address=number(c["address"],0x02000008,0x02400000-96)
        require(address%4==0, "invalid calibration address")
        # Stable public mount runtime address in overworld_mount_internal.h;
        # owner starts after its two native pointer fields.
        require(address==0x023BC744+8, "calibration address is not the mounted Owner")
        field,surface=struct.unpack_from("<II",before)
        require(field==mount["owner"]["fieldPointer"]==mount["ownerAfter"]["fieldPointer"]
                and surface==mount["surfacePointer"], "calibration native pointers differ")
        require(before[8:80]==raw_hex(mount["ownerHex"],72)==raw_hex(mount["profileHex"],144)[:72]
                and before[80:96]==raw_hex(mount["bindingHex"],16), "calibration Begin bytes differ")
        generation,phase,cancel,motion,reserved=struct.unpack_from("<IBBBB",before,96)
        require(generation==number(mount["sessionGeneration"],1) and phase==mount["mountPhase"]==1
                and (cancel,motion,reserved)==(0,0,0), "calibration mount state differs")
        start,end=c["beforeClock"],c["afterClock"]
        require(isinstance(start,dict) and set(start)=={"frame","nativeCycle"} and start==end,
                "guest clock changed during calibration")
        frame,cycle=number(start["frame"]),number(start["nativeCycle"],1)
        require(cycle==number(mount["returnNativeCycle"],1)
                and number(mount["entryNativeCycle"],1)<=cycle
                # _tap queues after this callback; completed() increments the
                # completed counter before completed_frame() publishes it.
                and number(event["frame"])==frame+1, "calibration clock differs from mount event")
        return dict(acceptedProof=False,scope="native Owner reader calibration only; not ordinary transfer or gameplay proof",
                    mountSequence=number(mount["sequence"],1),eventFrame=event["frame"],readerControl=deepcopy(c))
    except (KeyError,TypeError,IndexError,AttributeError) as error:
        raise ValueError("role transfer: missing or malformed calibration evidence") from error


def _inspect(events, initial, final):
    before, after = _actor(initial,"FOLLOWER"), _actor(final,"MOUNTED")
    require(before["handle"] == after["handle"] and initial["context"] == final["context"], "subject context changed")
    require(after.get("lane") == "OWNER" and type(after.get("inputOwnership")) is int
            and after["inputOwnership"] == 1, "mounted Owner/input ownership missing")
    require(before["engineIdentity"]["pointer"] == after["engineIdentity"]["pointer"], "endpoint object changed")
    require(before["behaviorFingerprint"] == after["behaviorFingerprint"], "endpoint profile identity changed")
    f0,f1 = number(initial["frame"]),number(final["frame"])
    c0,c1 = number(initial["nativeCycle"],1),number(final["nativeCycle"],1)
    require(0 <= f1-f0 <= 600 and 0 <= c1-c0 <= 4000, "endpoint clock span differs")
    require(isinstance(events,list) and 2 <= len(events) <= 128, "missing bounded transfer events")
    owner_reference = None
    def owner(value):
        nonlocal owner_reference
        public,source,engine = value["publicSubject"],value["sourceIdentity"],value["engineIdentity"]
        require(value["context"] == initial["context"] and public["handle"] == before["handle"]
                and public["role"] == "FOLLOWER" and all(public.get(k) == v for k,v in WITNESS.items()),
                "event subject differs")
        checked = actor_identity_checks({**public,"presentationAttached":True},source,engine,value["context"],7)
        require(all(checked.values()) and value["identityChecks"] == checked
                and source["form"] == public["form"] and source["level"] == public["level"]
                and engine["pointer"] == source["object"] == before["engineIdentity"]["pointer"],
                "event native owner differs")
        require(all(type(v) is bool for v in value["identityChecks"].values()), "coerced identity checks")
        field = number(value["fieldPointer"],0x02000000,0x023FFFFC)
        require(field % 4 == 0, "invalid field pointer")
        fixed = (field,number(value["heapGeneration"]),source,public["handle"])
        if owner_reference is None: owner_reference=deepcopy(fixed)
        require(fixed == owner_reference, "field/heap/source changed")
        require(public["behaviorFingerprint"] == before["behaviorFingerprint"], "getter fingerprint differs")
        return public
    previous_sequence,previous_frame,previous_cycle=0,f0,c0
    getters=[]; mounts=[]
    for event in events:
        require(event.get("kind") == "native-observation", "wrong event kind")
        d=event["data"]; name=d["observation"]
        require(name in ("role-profile-getter","role-profile-mount") and d["setupMode"] == "prepared",
                "wrong observation scope")
        frame,sequence=number(event["frame"]),number(d["sequence"],1)
        entry,returned=number(d["entryNativeCycle"],1),number(d["returnNativeCycle"],1)
        require(previous_sequence < sequence and previous_frame <= frame <= f1
                and previous_cycle <= entry <= returned <= c1, "event clock/order differs")
        require(number(d["entryActorFrame"]) <= number(d["returnActorFrame"]), "actor clock reversed")
        if "actorFrame" in initial and "actorFrame" in final:
            require(initial["actorFrame"] <= d["entryActorFrame"] <= d["returnActorFrame"] <= final["actorFrame"],
                    "event actor clock outside endpoints")
        previous_sequence,previous_frame,previous_cycle=sequence,frame,returned
        raw_hex(d["profileHex"],144);raw_hex(d["primitivesHex"],8)
        for key,size in (("profilePointer",144),("primitivesPointer",8)):
            p=number(d[key],0x02000000,0x027E3FB0)
            require(p%4==0 and (p+size<=0x02400000 or 0x027E0000<=p and p+size<=0x027E3FC0),
                    "invalid profile output pointer")
        if name=="role-profile-getter":
            require(not mounts and d["returnValue"] is None and d["nativeReturnKind"] == "void", "getter after mount or wrong return")
            owner(d["ownerBefore"]);owner(d["ownerAfter"])
            getters.append(event)
        else:
            require(type(d["returnValue"]) is int and d["returnValue"] == 1, "mount Begin failed")
            owner(d["owner"]);owner(d["ownerAfter"])
            mounts.append(event)
    require(len(mounts)==1 and getters, "unique mount/getter pair missing")
    mount=mounts[0]["data"]
    matches=[e for e in getters if all(e["data"][k]==mount[k] for k in ("profilePointer","primitivesPointer"))]
    require(matches, "matching getter pointer pair missing")
    getter=matches[-1]["data"]
    require(getter["profileHex"] == mount["profileHex"] and getter["primitivesHex"] == mount["primitivesHex"],
            "getter/Begin bytes differ")
    require(raw_hex(mount["ownerHex"],72) == raw_hex(getter["profileHex"],144)[:72], "stored Owner bytes differ")
    pid,species,map_id,map_gen,encounter,form,level,party,behavior = struct.unpack("<IHHHHBBBB",raw_hex(mount["bindingHex"],16))
    require((pid,species,form,level,party,map_id,map_gen,encounter)==(
        WITNESS["subjectIdentity"],WITNESS["species"],WITNESS["form"],WITNESS["level"],PARTY_SLOT,
        initial["context"]["mapId"],before["handle"]["mapGeneration"],before["handle"]["encounterGeneration"])
        and mount["partySlot"]==PARTY_SLOT, "mount binding differs")
    require(number(mount["sessionGeneration"],1)>0 and type(mount["mountPhase"]) is int
            and mount["mountPhase"]==1, "mount session not bound")
    return dict(acceptedProof=False,scope="prepared follower getter to mounted Owner transfer only; no Select/Hop/resolver-provenance claim",
        subject=deepcopy(WITNESS),partySlot=PARTY_SLOT,handle=deepcopy(before["handle"]),
        getterSequence=getter["sequence"],mountSequence=mount["sequence"],
        profileHex=getter["profileHex"],primitivesHex=getter["primitivesHex"],ownerHex=mount["ownerHex"],
        fieldPointer=owner_reference[0],heapGeneration=owner_reference[1],
        sessionGeneration=mount["sessionGeneration"],initialFrame=f0,finalFrame=f1)


def negative_controls(events, initial, final):
    """Copied-data controls of this checker, not native observer fault proof."""
    inspect_transfer(events,initial,final)
    results={}
    for name in ("missing-getter","missing-mount","wrong-profile","wrong-primitives",
                 "wrong-owner","wrong-pid","wrong-lane","wrong-clock"):
        e,i,f=deepcopy((events,initial,final))
        mount=next(x["data"] for x in e if x["data"]["observation"]=="role-profile-mount")
        if name.startswith("missing-"):
            kind="role-profile-"+name.removeprefix("missing-")
            e=[x for x in e if x["data"]["observation"]!=kind]
        elif name in ("wrong-profile","wrong-primitives","wrong-owner"):
            key={"wrong-profile":"profileHex","wrong-primitives":"primitivesHex","wrong-owner":"ownerHex"}[name]
            b=bytearray.fromhex(mount[key]);b[0]^=1;mount[key]=b.hex()
        elif name=="wrong-pid":
            next(a for a in f["actors"] if a.get("role")=="MOUNTED")["subjectIdentity"]^=1
        elif name=="wrong-lane":
            next(a for a in f["actors"] if a.get("role")=="MOUNTED")["lane"]="TIRED"
        else: mount["returnNativeCycle"]=f["nativeCycle"]+1
        try:
            inspect_transfer(e,i,f)
        except ValueError as error:
            results[name]={"rejected":True,"reason":str(error)}
        else:
            raise ValueError("role transfer: copied-data control accepted: "+name)
    return dict(scope="copied-data evaluator controls only; not live observer faults",controls=results)
