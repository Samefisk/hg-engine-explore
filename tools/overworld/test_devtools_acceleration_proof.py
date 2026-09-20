"""Synthetic controller receipt controls; no emulator or gameplay acceptance."""
from copy import deepcopy
import struct
import unittest

from tools.overworld.devtools_acceleration_proof import checked_reset_receipt
from tools.overworld.devtools_acceleration_measurement import POLICY_FIELDS
from tools.overworld.test_devtools_acceleration_measurement import fixture


def proof_fixture(role="WILD"):
    _snapshot, inner, _rows = fixture(role)
    target, address, field, sp = 0x02030202, 0x02040000, 0x02060000, 0x0207F000
    service = dict(address=0x02030000,
        entryHex=struct.pack(
            "<IHHII", 0x504D574F, 5, 16, 0x02030100, 0x02030300).hex(),
        tableHex=struct.pack("<6I", 1, 3, 5, target | 1, 7, 9).hex(),
        reduceWalkAddress=target | 1, entrySha256="ab" * 32)
    inner.update(serviceIdentity=service, fieldPointer=field, heapGeneration=0)
    for endpoint in (inner["before"], inner["after"]):
        endpoint["snapshot"]["fieldControl"] = {"fieldPointer": field}
        raw = bytes.fromhex(endpoint["policyHex"])
        endpoint["policy"] = {key: raw[index] for key, index in POLICY_FIELDS.items()}
    snapshot = deepcopy(inner["after"]["snapshot"])
    receipt = dict(value=inner, snapshot=deepcopy(snapshot), boundary="native-field-command-trampoline",
        preparedOnly=True, acceptedProof=False, firstBadCheckpoint=None, firstInvalidThreadSwitch=None,
        nativeHeapAdaptation=[], events=[],
        setupBoundary=dict(frame=snapshot["frame"], nativeCycle=snapshot["nativeCycle"],
            endpointNativeCycle=snapshot["nativeCycle"], eventsDrained=True, traceSequences={"1": 0}),
        trampoline=dict(address=address, bytes=1536, heapId=11, lifetime="field-system-heap11",
            fieldPointer=field, heapGeneration=0, codeSha256="cd" * 32),
        stackOwnership=dict(callSp=sp, hostRestoredFrameBytes=0, nativeFrameBytes=80, scratchBytes=268,
            thread=dict(pointer=0x02070000, id=1, state=1, mode=31, irqDepth=0,
                stackTop=0x0207C000, stackBottom=0x02080000,
                topGuard=0x7BF9DD5B, bottomGuard=0xFDDB597D)),
        calls=[dict(routine="reduce_walk", address=target, requestedArguments=[address + 0x210],
            entryArguments=[address + 0x210], returnValue=1, entryStack=sp, entryLink=address + 0x4C,
            entryCpsr=0x3F, entryBoundary="native-trampoline-BLX-entry")])
    return {"command": "walk-policy.reset", "receipt": receipt, "snapshot": snapshot}, \
        deepcopy(inner["subject"]), {"callAddresses": {"reduce_walk": target}, "serviceIdentity": deepcopy(service)}


class ResetProofTests(unittest.TestCase):
    def test_exact_wild_and_mounted_receipt_no_motion_credit(self):
        for role in ("WILD", "MOUNTED"):
            row, subject, oracle = proof_fixture(role)
            result = checked_reset_receipt(row, subject, oracle=oracle)
            self.assertFalse(result["acceptedProof"])
            self.assertEqual(result["observedFrames"], 0)
            self.assertEqual(result["nativeCalls"], 1)
            result["reset"]["completed"] = False
            self.assertTrue(row["receipt"]["value"]["completed"])
            row["command"] = "acceleration.begin"
            self.assertEqual(checked_reset_receipt(row, subject, oracle=oracle)["nativeCalls"], 1)

    def test_call_and_oracle_controls(self):
        for fault in ("missing", "extra", "target", "argument", "entry", "return", "service", "operation"):
            row, subject, oracle = proof_fixture()
            receipt = row["receipt"]
            if fault == "missing": receipt["calls"] = []
            elif fault == "extra": receipt["calls"].append(deepcopy(receipt["calls"][0]))
            elif fault == "target": receipt["calls"][0]["address"] += 2
            elif fault == "argument": receipt["calls"][0]["requestedArguments"][0] += 4
            elif fault == "entry": receipt["calls"][0]["entryArguments"][0] += 4
            elif fault == "return": receipt["calls"][0]["returnValue"] = True
            elif fault == "service": receipt["value"]["serviceIdentity"]["entrySha256"] = "ff" * 32
            else:
                raw = bytearray.fromhex(receipt["value"]["requestHex"]); raw[9] = 1
                receipt["value"]["requestHex"] = receipt["value"]["responseHex"] = raw.hex()
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                checked_reset_receipt(row, subject, oracle=oracle)

    def test_thread_owner_cleanup_and_boundary_controls(self):
        for fault in ("field", "heap", "thread", "guard", "stack", "link", "mode", "checkpoint", "scratch", "drain", "clock"):
            row, subject, oracle = proof_fixture()
            receipt = row["receipt"]
            if fault == "field": receipt["trampoline"]["fieldPointer"] += 4
            elif fault == "heap": receipt["value"]["heapGeneration"] += 1
            elif fault == "thread": receipt["stackOwnership"]["thread"]["state"] = 2
            elif fault == "guard": receipt["stackOwnership"]["thread"]["bottomGuard"] ^= 1
            elif fault == "stack": receipt["calls"][0]["entryStack"] += 8
            elif fault == "link": receipt["calls"][0]["entryLink"] += 2
            elif fault == "mode": receipt["calls"][0]["entryCpsr"] = 0x13
            elif fault == "checkpoint": receipt["firstBadCheckpoint"] = {"bad": True}
            elif fault == "scratch": receipt["value"]["scratchRestored"] = False
            elif fault == "drain": receipt["setupBoundary"]["eventsDrained"] = False
            else: receipt["setupBoundary"]["nativeCycle"] += 1
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                checked_reset_receipt(row, subject, oracle=oracle)

    def test_subject_and_policy_controls(self):
        for fault in ("generation", "engine", "fingerprint", "decoded", "idle", "keys"):
            row, subject, oracle = proof_fixture()
            value = row["receipt"]["value"]
            if fault == "generation": subject["authorityGeneration"] += 1
            elif fault == "engine": subject["engineIdentity"]["pointer"] += 4
            elif fault == "fingerprint":
                for endpoint in (value["before"], value["after"]):
                    raw = bytearray.fromhex(endpoint["policyHex"]); raw[8] ^= 1
                    endpoint["policyHex"] = raw.hex()
            elif fault == "decoded": value["after"]["policy"]["speed"] = 1
            elif fault == "idle":
                for endpoint in (value["before"], value["after"]):
                    endpoint["actor"]["reservationId"] = 1
                    endpoint["snapshot"]["actors"][0]["reservationId"] = 1
            else:
                for endpoint in (value["before"], value["after"]): endpoint["inputs"]["heldKeys"] = 16
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                checked_reset_receipt(row, subject, oracle=oracle)


if __name__ == "__main__":
    unittest.main()
