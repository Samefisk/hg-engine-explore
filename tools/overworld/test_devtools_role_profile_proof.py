"""Synthetic coherent endpoints, plus optional retained native transfer bytes."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import unittest

from tools.overworld.devtools_role_profile_proof import inspect_transfer,inspect_reader_control,negative_controls,WITNESS
from tools.overworld import test_devtools_role_profile as reader_tests


def endpoints(events, witness=WITNESS):
    # Explicitly synthetic host snapshots, NOT saved native endpoint evidence.
    owner=events[0]["data"]["ownerBefore"]
    actor=dict(**deepcopy(owner["publicSubject"]),active=True,presentationAttached=True,identityVerified=True,
        engineIdentity=deepcopy(owner["engineIdentity"]),lane="OWNER",inputOwnership=0)
    mon=dict(slot=2,species=witness["species"],personality=witness["subjectIdentity"],
             form=witness["form"],level=witness["level"],
             identityVerified=True,isEgg=False,hp=1,status=0)
    initial=dict(frame=events[0]["frame"]-1,nativeCycle=events[0]["data"]["entryNativeCycle"]-1,
        fieldAvailable=True,observationBoundary="main-task-queue-completion",context=deepcopy(owner["context"]),
        actors=[actor],party=[{}, {},mon],selector={"activeFollowerPartySlot":2})
    final=deepcopy(initial);final.update(frame=events[-1]["frame"]+1,nativeCycle=events[-1]["data"]["returnNativeCycle"]+2)
    final["actors"][0].update(role="MOUNTED",inputOwnership=1)
    return initial,final


class RoleProfileProofTests(unittest.TestCase):
    def calibrated_fixture(self):
        events,initial,final=self.fixture()
        m=events[-1]["data"]
        clean=struct.pack("<II",m["owner"]["fieldPointer"],m["surfacePointer"])+bytes.fromhex(m["ownerHex"])+bytes.fromhex(m["bindingHex"])+struct.pack("<IBBBB",m["sessionGeneration"],1,0,0,0)
        fault=bytearray(clean);fault[8]^=1
        m["readerControl"]=dict(acceptedProof=False,guestAdvanced=False,rejected=True,writes=2,
            reason="role profile: mounted Owner snapshot differs from Begin inputs",address=0x023BC74C,
            beforeSnapshotHex=clean.hex(),faultSnapshotHex=fault.hex(),restoredSnapshotHex=clean.hex(),
            beforeHex=clean[8:9].hex(),faultHex=fault[8:9].hex(),restoredHex=clean[8:9].hex(),
            beforeClock=dict(frame=733,nativeCycle=1860),afterClock=dict(frame=733,nativeCycle=1860))
        return events,initial,final

    def fixture(self, witness=WITNESS):
        r,s,a,source,engine,regs,put,_=reader_tests.RoleProfileTests().fixture()
        a.update(witness);source.update(species=witness["species"],personality=witness["subjectIdentity"],
                                        form=witness["form"],level=witness["level"])
        g=r.getter_after(r.getter_before(),{})
        follower_profile=bytearray.fromhex(g["profileHex"])
        follower_profile[11]^=1
        g["profileHex"]=follower_profile.hex()
        mounted_profile=bytes(range(144))
        put(regs.r2,mounted_profile)
        regs.r0=s.field_pointer();regs.r1=0x02212000;regs.r3=0x02213000
        binding=struct.pack("<IHHHHBBBB",witness["subjectIdentity"],witness["species"],33,3,4,
                            witness["form"],witness["level"],2,0)
        transaction=0x027E3100
        put(regs.r1,binding);put(regs.sp,struct.pack("<I",transaction))
        put(transaction,struct.pack("<IIII",3,4,0,0))
        before=r.mount_before()
        put(transaction,struct.pack("<IIII",3,4,1,2))
        put(r.mount_state,struct.pack("<II",s.field_pointer(),0x02213000)+mounted_profile[:72]+binding+
            struct.pack("<IBBBB",7,1,0,0,0))
        a.update(behaviorFingerprint=3,matchedLayerMask=4)
        m=r.mount_after(before,{"returnValue":1})
        events=[]
        for seq,name,data in ((194,"role-profile-getter",g),(198,"role-profile-mount",m)):
            events.append(dict(frame=734,kind="native-observation",data={
                "observation":name,"sequence":seq,"entryActorFrame":300,"returnActorFrame":300,
                "entryNativeCycle":1860,"returnNativeCycle":1860,"setupMode":"prepared",
                "returnValue":None if name.endswith("getter") else 1,**data}))
        initial,final=endpoints(events,witness)
        final["actors"][0]["behaviorFingerprint"]=3
        final["actors"][0]["matchedLayerMask"]=4
        return events,initial,final

    def test_exact_transfer_is_detached_and_not_input_or_motion_acceptance(self):
        e,i,f=self.fixture();old=deepcopy((e,i,f));p=inspect_transfer(e,i,f)
        self.assertFalse(p["acceptedProof"])
        self.assertEqual(p["ownerHex"],bytes(range(72)).hex())
        self.assertEqual(p["getterSequence"],194)
        self.assertEqual((e,i,f),old)

    def test_wrong_owner_bytes_missing_calls_and_clock_controls(self):
        for fault in ("pid","object","role","lane","ownership","profile","mounted-policy","ownerbytes",
                      "missing-getter","missing-mount","duplicate-mount","clock","stale","party","pointer","heap"):
            e,i,f=self.fixture();g=e[0]["data"];m=e[1]["data"]
            if fault=="pid":f["actors"][0]["subjectIdentity"]+=1
            if fault=="object":m["ownerAfter"]["sourceIdentity"]["object"]+=4
            if fault=="role":m["owner"]["publicSubject"]["role"]="WILD"
            if fault=="lane":f["actors"][0]["lane"]="TIRED"
            if fault=="ownership":f["actors"][0]["inputOwnership"]=0
            if fault=="profile":m["profileHex"]="ff"+m["profileHex"][2:]
            if fault=="mounted-policy":m["mountedPolicyFingerprint"]^=1
            if fault=="ownerbytes":m["ownerHex"]="ff"+m["ownerHex"][2:]
            if fault=="missing-getter":e.pop(0)
            if fault=="missing-mount":e.pop()
            if fault=="duplicate-mount":e.append(deepcopy(e[-1]))
            if fault=="clock":m["entryNativeCycle"]-=1
            if fault=="stale":f["context"]["mapGeneration"]+=1
            if fault=="party":f["party"][2]["personality"]+=1
            if fault=="pointer":m["profilePointer"]=1
            if fault=="heap":m["owner"]["heapGeneration"]+=1
            with self.subTest(fault=fault),self.assertRaises(ValueError):inspect_transfer(e,i,f)

    def test_retained_native_events_with_explicit_synthetic_endpoints(self):
        path=Path(__file__).resolve().parents[2]/"build/overworld-devtools/session-2i7uuq11/event-details-734e742219ec.json"
        if not path.is_file():self.skipTest("optional retained native transfer is absent")
        original=path.read_bytes()
        events=json.loads(original)["receipt"]["profileObservation"]["events"]
        initial,final=endpoints(events)
        # This old-ROM receipt bound Follower bytes as Mounted. It is retained
        # as a rejected regression witness, not current mounted proof.
        with self.assertRaisesRegex(ValueError,"Follower-only profile"):
            inspect_transfer(events,initial,final)
        self.assertEqual(path.read_bytes(),original)

    def test_copied_controls_and_no_input_mutation(self):
        e,i,f=self.fixture();original=deepcopy((e,i,f))
        result=negative_controls(e,i,f)
        self.assertEqual(len(result["controls"]),8)
        self.assertTrue(all(c["rejected"] for c in result["controls"].values()))
        self.assertEqual((e,i,f),original)

    def test_calibration_requires_explicit_opt_in_and_detached_native_evidence(self):
        e,i,f=self.calibrated_fixture();original=deepcopy((e,i,f))
        with self.assertRaisesRegex(ValueError,"not ordinary transfer"):inspect_transfer(e,i,f)
        self.assertFalse(inspect_transfer(e,i,f,allow_reader_control=True)["acceptedProof"])
        result=inspect_reader_control(e)
        self.assertFalse(result["acceptedProof"])
        result["readerControl"]["address"]=0
        self.assertEqual((e,i,f),original)

    def test_calibration_wrong_bytes_target_flags_clock_and_missing_controls(self):
        for fault in ("extra-byte","restored","address","writes","clock","event-frame","wrong-reason",
                      "accepted","advance","missing","duplicate","binding","state","owner-byte"):
            e,i,f=self.calibrated_fixture();m=e[-1]["data"];c=m["readerControl"]
            if fault=="extra-byte":
                b=bytearray.fromhex(c["faultSnapshotHex"]);b[9]^=1;c["faultSnapshotHex"]=b.hex()
            if fault=="restored":c["restoredSnapshotHex"]=c["faultSnapshotHex"]
            if fault=="address":c["address"]+=4
            if fault=="writes":c["writes"]=1
            if fault=="clock":c["afterClock"]["nativeCycle"]+=1
            if fault=="event-frame":e[-1]["frame"]+=2
            if fault=="wrong-reason":c["reason"]="unrelated"
            if fault=="accepted":c["acceptedProof"]=True
            if fault=="advance":c["guestAdvanced"]=True
            if fault=="missing":del m["readerControl"]
            if fault=="duplicate":e.append(deepcopy(e[-1]))
            if fault=="binding":m["bindingHex"]="ff"+m["bindingHex"][2:]
            if fault=="state":m["sessionGeneration"]+=1
            if fault=="owner-byte":c["faultHex"]=c["beforeHex"]
            with self.subTest(fault=fault),self.assertRaises(ValueError):inspect_reader_control(e)

    def test_control_address_anchor_is_the_real_public_runtime_symbol(self):
        header=(Path(__file__).resolve().parents[2]/"include/overworld_mount_internal.h").read_text()
        self.assertIn("#define OVERWORLD_MOUNT_RUNTIME_STATE_ADDR 0x023BC744",header)


if __name__=="__main__":unittest.main()
