"""Controller receipt controls; synthetic fixtures grant no native proof."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tools.overworld.devtools_resolver_proof import resolver_measurements, negative_controls, NAMES
from tools.overworld.devtools_resolver_parity import CASE_NAMES
from tools.overworld.devtools_resolver_probe import REQUEST, RESULT, TRACE
from tools.overworld import test_devtools_resolver_parity as parity_tests


class ResolverProofTests(unittest.TestCase):
    def fixture(self):
        vectors, natives, host, identities = parity_tests.ResolverParityTests().fixture()
        oracle = dict(vectors=vectors, hostResults=host, blobIdentity=identities["blob_identity"],
            serviceIdentity=identities["service_identity"], callAddresses=dict(
                allocate_work_memory=0x0201AA8C, resolve_behavior=0x023B0000, free=0x0201AB0C))
        work, source, trampoline, sp = 0x02210000, 0x02200000, 0x02220000, 0x027E0000
        for n in natives:
            n.update(dispatchClock=dict(frame=10,nativeCycle=25), returnClock=dict(frame=10,nativeCycle=25))
        calls=[]
        for name,args,result in [("allocate_work_memory",[11,8000],work)]+[
                ("resolve_behavior",[source,100,work+REQUEST,work+RESULT,work+TRACE],0)
                ] * len(CASE_NAMES) + [("free",[work],128)]:
            calls.append(dict(routine=name,address=oracle["callAddresses"][name],requestedArguments=args[:],
                entryArguments=args[:],entryStack=sp,entryLink=trampoline+0x4C,entryCpsr=63,
                entryBoundary="native-trampoline-BLX-entry",returnValue=result))
        receipt=dict(preparedOnly=True,acceptedProof=False,boundary="native-field-command-trampoline",
            firstBadCheckpoint=None,firstInvalidThreadSwitch=None,nativeHeapAdaptation=[],calls=calls,
            value=dict(completed=True,acceptedProof=False,receipts=natives,
                allocation=dict(released=True,heapId=11,bytes=8000,pointer=work)),
            naturalDiscovery=dict(blobAddress=source,blobSize=100,fieldPointer=0x02230000,heapGeneration=0,
                status=0,requestHex=bytes(44).hex(),entryNativeCycle=20,returnNativeCycle=20),
            trampoline=dict(address=trampoline,bytes=1536,heapId=11,lifetime="field-system-heap11",
                fieldPointer=0x02230000,heapGeneration=0,codeSha256="c"*64),
            stackOwnership=dict(callSp=sp,hostRestoredFrameBytes=0,nativeFrameBytes=80,scratchBytes=268,
                thread=dict(mode=31,irqDepth=0,stackTop=sp-1000,stackBottom=sp+1000)),
            setupBoundary=dict(eventsDrained=True,traceSequences={},frame=12,nativeCycle=28,endpointNativeCycle=28))
        test=dict(mode="prepared",setup=[dict(id="probe",op="resolver.probe",args={})],actions=[])
        rows=[dict(phase="setup",initialSnapshot=dict(frame=10,nativeCycle=24)),
              dict(phase="setup",action="probe",command="resolver.probe",receipt=receipt,
                   snapshot=dict(frame=12,nativeCycle=28))]
        return test,rows,oracle

    def check(self,test,rows,oracle):
        return resolver_measurements(test,iter(rows),{},Path(__file__).resolve().parents[2],oracle=oracle)

    def test_same_cycle_calls_and_all_eight_original_measurements(self):
        t,r,o=self.fixture();before=deepcopy((t,r,o)); result=self.check(t,r,o)
        self.assertEqual([m["name"] for m in result["measurements"]],list(NAMES))
        self.assertEqual(result["observedFrames"],1)
        self.assertEqual(result["completedGameFrames"],0)
        self.assertNotIn("acceptedProof",result)
        self.assertEqual(result["caseProof"]["caseCount"],len(CASE_NAMES))
        self.assertEqual((t,r,o),before)

    def test_damaged_native_evidence_cannot_authorize_parity(self):
        for fault in ("service","blob","return","count","trace","request","free","unreleased",
                      "entry","stack","owner","clock","boundary","discovery","unknown","duplicate"):
            t,r,o=self.fixture();p=r[1]["receipt"];v=p["value"];n=v["receipts"][0]
            if fault=="service": n["serviceIdentity"]["entrySha256"]="d"*64
            if fault=="blob": n["blobIdentity"]["sha256"]="d"*64
            if fault=="return": p["calls"][1]["returnValue"]=1
            if fault=="count": v["receipts"].pop()
            if fault=="trace": n["trace"].reverse()
            if fault=="request": n["requestHex"]="00"*44
            if fault=="free": p["calls"].pop()
            if fault=="unreleased": v["allocation"]["released"]=False
            if fault=="entry": p["calls"][1]["entryArguments"][0]+=4
            if fault=="stack": p["calls"][1]["entryStack"]+=8
            if fault=="owner": p["trampoline"]["heapGeneration"]+=1
            if fault=="clock": n["returnClock"]["nativeCycle"]=29
            if fault=="boundary": p["setupBoundary"]["eventsDrained"]=False
            if fault=="discovery": p["naturalDiscovery"]["returnNativeCycle"]=26
            if fault=="unknown": r[1]["command"]="party"
            if fault=="duplicate": r.append(deepcopy(r[1]))
            with self.subTest(fault=fault),self.assertRaises(ValueError): self.check(t,r,o)

    def test_current_host_against_immutable_native_receipt(self):
        # Optional local integration: use the existing host executable, never build.
        import hashlib
        import importlib.util
        from tools.overworld.devtools_runtime import _elf_code
        root=Path(__file__).resolve().parents[2]
        path=root/"build/overworld-devtools/session-5k6z3obo/event-details-55e1848812a0.json"
        executable=root/"build/overworld_behavior_resolver_host"
        if not path.is_file() or not executable.is_file(): self.skipTest("retained native receipt/host absent")
        t,r,o=self.fixture();p=json.loads(path.read_text())["receipt"]
        descriptor=json.loads((root/"build/overworld-system.debug.json").read_text())
        service=next(s for s in descriptor["privateServices"] if s["name"]=="resolver")
        address=service["callbacks"]["resolve"] & ~1
        blob=(root/"build/OverworldWildBehaviorData.bin").read_bytes()
        o["blobIdentity"]=dict(size=len(blob),sha256=hashlib.sha256(blob).hexdigest())
        o["serviceIdentity"]=dict(magic=0x5250574F,version=service["version"],size=service["size"],
            resolveAddress=address|1,entrySha256=hashlib.sha256(_elf_code(
                root/"build/overworld_actor_system_overlay_linked.o",address,32)).hexdigest())
        o["callAddresses"]["resolve_behavior"]=address
        spec=importlib.util.spec_from_file_location("resolver_proof_host",root/"tools/overworld-viewer-v2/native_resolver.py")
        adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
        o["hostResults"]=adapter.resolve_many(root/"build/OverworldWildBehaviorData.bin",
            [v["request"] for v in o["vectors"]],root=root,executable=executable)
        r[0]["initialSnapshot"]=dict(frame=732,nativeCycle=1857)
        r[1].update(receipt=p,snapshot=dict(frame=734,nativeCycle=1861))
        self.assertEqual(self.check(t,r,o)["caseProof"]["caseCount"],len(CASE_NAMES))

    def test_neutral_wait_raw_clock_checks_and_no_work_credit(self):
        t,r,o=self.fixture()
        t["actions"]=[dict(id="settle",op="wait",args={})]
        sample=dict(frame=13,nativeCycle=29,fieldAvailable=True)
        row=dict(phase="observe",action="settle",samples=[sample],completedGameFrames=1,
            nativeCycles=1,observedFieldFrames=1,events=[],cycleIntervals=[dict(
                completedGameFrame=13,cpuNs=100,wallNs=100)])
        r.append(row)
        self.assertEqual(self.check(t,r,o)["observedFrames"],1)
        row["samples"][0]["nativeCycle"]=30
        with self.assertRaises(ValueError): self.check(t,r,o)

    def test_missing_bridge_evidence_and_extra_trace_fail(self):
        for fault in ("checkpoint", "heap", "phase", "trace-capacity"):
            t,r,o=self.fixture();p=r[1]["receipt"]
            if fault=="checkpoint": del p["firstBadCheckpoint"]
            if fault=="heap": p["nativeHeapAdaptation"]=[{}]
            if fault=="phase": r[1]["phase"]="observe"
            if fault=="trace-capacity": p["value"]["receipts"][0]["trace"] *= 49
            with self.subTest(fault=fault),self.assertRaises(ValueError):self.check(t,r,o)

    def test_seven_copied_data_controls_use_exact_reasons_and_preserve_source(self):
        t,r,o=self.fixture();original=deepcopy((t,r,o))
        result=negative_controls(t,iter(r),{},Path(__file__).resolve().parents[2],oracle=o)
        self.assertEqual(len(result["controls"]),7)
        self.assertTrue(all(c["rejected"] for c in result["controls"].values()))
        self.assertIn("not live observer faults",result["scope"])
        self.assertEqual((t,r,o),original)

    def test_controls_do_not_relabel_existing_bad_stream_as_successful_detection(self):
        t,r,o=self.fixture();r[1]["receipt"]["calls"][1]["returnValue"]=1
        with self.assertRaisesRegex(ValueError,"native return differs"):
            negative_controls(t,r,{},Path(__file__).resolve().parents[2],oracle=o)

    def test_real_case_clock_span_and_optional_worker_endpoint_agreement(self):
        t,r,o=self.fixture();p=r[1]["receipt"]
        p["value"]["receipts"][-1]["returnClock"]=dict(frame=11,nativeCycle=26)
        p["snapshot"]=deepcopy(r[1]["snapshot"])
        result=self.check(t,r,o)
        self.assertEqual(result["completedGameFrames"],1)
        self.assertEqual(result["observedFrames"],2)
        p["snapshot"]["frame"]+=1
        with self.assertRaisesRegex(ValueError,"worker and row endpoints differ"):self.check(t,r,o)


if __name__=="__main__":unittest.main()
