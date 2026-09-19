"""Small raw command fixtures; no synthetic result can grant live proof."""
from copy import deepcopy
import unittest

from tools.overworld.devtools_resolver_measurement import ResolverMeasurement
from tools.overworld.devtools_resolver_parity import CASE_NAMES


class ResolverMeasurementTests(unittest.TestCase):
    def fixture(self):
        pointer = 0x02040000
        cases = [dict(name=name, status=0, requestHex="00"*20, resultHex="00"*256,
                      traceDropped=0, trace=[dict(sourceIndex=0, lane=0, kind=2, flags=3, profileHex="00"*72)],
                      blobIdentity={"size":100}, serviceIdentity={"version":1},
                      dispatchClock={"frame":900,"nativeCycle":2000}, returnClock={"frame":900,"nativeCycle":2000})
                 for name in CASE_NAMES]
        calls = [dict(routine="allocate_work_memory", requestedArguments=[11,8000], returnValue=pointer)]
        for _ in cases:
            args = [0x02020000,100,pointer+16,pointer+36,pointer+292]
            calls.append(dict(routine="resolve_behavior", requestedArguments=args, entryArguments=args[:],returnValue=0))
        calls.append(dict(routine="free", requestedArguments=[pointer],returnValue=0))
        snapshot = {"frame":901,"nativeCycle":2002}
        receipt = dict(snapshot=snapshot,events=[],setupBoundary=dict(frame=901,nativeCycle=2002,eventsDrained=True),
            boundary="native-field-command-trampoline",preparedOnly=True,calls=calls,value=dict(
                completed=True,acceptedProof=False,receipts=cases,
                allocation=dict(pointer=pointer,heapId=11,bytes=8000,released=True)))
        return dict(command="resolver.probe",phase="observe",action="parity",receipt=receipt,snapshot=snapshot)

    def test_one_native_cycle_no_boot_padding_and_detached_result(self):
        meter = ResolverMeasurement()
        meter.observe_record({"initialSnapshot":{"frame":0,"nativeCycle":0}})
        row = self.fixture(); original=deepcopy(row)
        result = meter.observe_record(row)
        self.assertTrue(result["ready"]); self.assertTrue(result["passed"])
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(result["observedFrames"],1)
        self.assertEqual(result["observedFrameUnit"],"native-resolver-cycles")
        self.assertEqual(result["completedGameFrames"],0)
        result["receipt"].clear()
        self.assertEqual(row,original)
        self.assertTrue(meter.finish()["passed"])

    def test_exact_command_and_duplicate_required(self):
        meter=ResolverMeasurement(); meter.observe_record({"command":"inspect"})
        self.assertEqual(meter.finish()["failures"][0]["code"],"resolver-probe-missing")
        meter=ResolverMeasurement(); row=self.fixture()
        meter.observe_record(row)
        self.assertFalse(meter.observe_record(row)["passed"])

    def test_bad_case_free_status_clock_and_fatal_controls(self):
        for fault in ("missing-case","status","short","drop","free","free-call","fatal","bridge",
                      "arguments","future","backwards","endpoint"):
            with self.subTest(fault=fault):
                row=self.fixture(); receipt=row["receipt"]; bridge=receipt; probe=bridge["value"]
                if fault=="missing-case":probe["receipts"].pop()
                if fault=="status":probe["receipts"][0]["status"]=1
                if fault=="short":probe["receipts"][0]["resultHex"]="00"
                if fault=="drop":probe["receipts"][0]["traceDropped"]=1
                if fault=="free":probe["allocation"]["released"]=False
                if fault=="free-call":bridge["calls"].pop()
                if fault=="fatal":receipt["fatal"]=True
                if fault=="bridge":bridge["firstBadCheckpoint"]={"target":1}
                if fault=="arguments":bridge["calls"][1]["entryArguments"][2]+=4
                if fault=="future":probe["receipts"][0]["returnClock"]["nativeCycle"]=2003
                if fault=="backwards":probe["receipts"][0]["returnClock"]["nativeCycle"]=1999
                if fault=="endpoint":receipt["setupBoundary"]["frame"]+=1
                result=ResolverMeasurement().observe_record(row)
                self.assertFalse(result["passed"])
                self.assertEqual(result["failures"][0]["code"],"resolver-probe-invalid")
