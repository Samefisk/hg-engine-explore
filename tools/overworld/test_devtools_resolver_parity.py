"""Synthetic comparator controls; no output here is a native gameplay receipt."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
import subprocess
import tempfile

from tools.overworld.devtools_resolver_parity import (
    CASE_NAMES, METADATA, compare_resolver_parity, host_result_bytes, request_bytes,
)


class ResolverParityTests(unittest.TestCase):
    def fixture(self):
        root = Path(__file__).resolve().parents[2]
        vectors = json.loads((root / "tools/overworld/native/behavior_resolver_golden.json").read_text())["vectors"]
        self.assertEqual(tuple(v["name"] for v in vectors), CASE_NAMES)
        blob = {"size": 100, "sha256": "a" * 64}
        service = dict(magic=0x5250574F, version=1, size=16, resolveAddress=0x023B0001, entrySha256="b" * 64)
        host = []; native = []
        for index, vector in enumerate(vectors):
            result = {key: index for key in METADATA}
            result.update(status=0, profileHex=bytes([index] * 216).hex(), primitivesHex=bytes([index] * 11).hex(),
                traceDropped=0, trace=[dict(sourceIndex=0, lane=0, kind=2, flags=3, profileHex="00" * 72),
                                       dict(sourceIndex=1, lane=1, kind=3, flags=3, profileHex="01" * 72)])
            host.append(result)
            native.append(dict(name=vector["name"], requestHex=request_bytes(vector["request"]).hex(),
                resultHex=host_result_bytes(result).hex(), status=0, traceDropped=0, trace=deepcopy(result["trace"]),
                blobIdentity=deepcopy(blob), serviceIdentity=deepcopy(service)))
        return vectors, native, host, dict(blob_identity=blob, service_identity=service)

    def test_exact_seven_and_detached_result_not_live_proof(self):
        vectors, native, host, identities = self.fixture()
        original = deepcopy((vectors, native, host, identities))
        result = compare_resolver_parity(vectors, native, host, **identities)
        self.assertTrue(result["passed"]); self.assertFalse(result["acceptedProof"])
        self.assertEqual(result["caseCount"], 7)
        result["blobIdentity"]["size"] = 1
        self.assertEqual((vectors, native, host, identities), original)

    def test_every_result_byte_is_compared(self):
        vectors, native, host, identities = self.fixture()
        for offset in range(256):
            changed = deepcopy(native)
            raw = bytearray.fromhex(changed[0]["resultHex"]); raw[offset] ^= 1
            changed[0]["resultHex"] = raw.hex()
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, "full result"):
                compare_resolver_parity(vectors, changed, host, **identities)

    def test_request_status_provenance_identity_and_case_controls(self):
        for fault in ("request", "status", "boolean-status", "trace-order", "trace-missing", "trace-dropped",
                      "trace-profile", "blob", "service", "missing", "duplicate", "wrong-host", "short-result"):
            vectors, native, host, identities = self.fixture()
            if fault == "request": native[0]["requestHex"] = "ff" * 20
            if fault == "status": native[0]["status"] = 1
            if fault == "boolean-status": native[0]["status"] = False
            if fault == "trace-order": native[0]["trace"].reverse()
            if fault == "trace-missing": native[0]["trace"] = []
            if fault == "trace-dropped": native[0]["traceDropped"] = 1
            if fault == "trace-profile": native[0]["trace"][0]["profileHex"] = "ff" * 72
            if fault == "blob": native[0]["blobIdentity"]["size"] += 1
            if fault == "service": native[0]["serviceIdentity"]["resolveAddress"] += 2
            if fault == "missing": native.pop()
            if fault == "duplicate": native[1] = deepcopy(native[0])
            if fault == "wrong-host": host[0]["fingerprint"] += 1
            if fault == "short-result": native[0]["resultHex"] = "00"
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                compare_resolver_parity(vectors, native, host, **identities)

    def test_request_layout_defaults_and_public_header_anchor(self):
        raw = request_bytes({"species": 155})
        self.assertEqual(len(raw), 20)
        self.assertEqual(int.from_bytes(raw[:2], "little"), 155)
        self.assertEqual(raw[8:12], bytes([1, 0, 0, 0]))
        self.assertEqual(raw[16:], bytes([255, 0, 0, 0]))
        root = Path(__file__).resolve().parents[2]
        header = (root / "include/overworld_behavior_resolver.h").read_text()
        body = header.split("typedef struct BehaviorResolveResult {", 1)[1].split("} BehaviorResolveResult;", 1)[0]
        positions = [body.index(key + ";") for key in METADATA]
        self.assertEqual(positions, sorted(positions))

    def test_result_bytes_match_compiled_public_layout(self):
        root = Path(__file__).resolve().parents[2]
        code = '''#include <stdio.h>
#include <string.h>
#include "overworld_behavior_resolver.h"
int main(void) {
 BehaviorResolveResult r; memset(&r,0,sizeof r);
 memset(&r.profile,17,sizeof r.profile); memset(&r.primitives,34,sizeof r.primitives);
 r.behaviorClass=3; r.behaviorLimitKey=4; r.speciesClassRuleIndex=5;
 r.matchedClassRuleMask=6; r.matchedOverrideMask=7; r.forcedOverrideMask=8;
 r.conditionalOverrideMask=9; r.appliedOverrideMask=10; r.fingerprint=11;
 return fwrite(&r,1,sizeof r,stdout)==sizeof r ? 0 : 1;
}'''
        with tempfile.TemporaryDirectory() as directory:
            executable = str(Path(directory) / "layout")
            subprocess.run(["cc", "-DOVERWORLD_BEHAVIOR_HOST", "-I", str(root / "include"),
                            "-x", "c", "-", "-o", executable], input=code, text=True,
                           capture_output=True, check=True)
            native = subprocess.run([executable], capture_output=True, check=True).stdout
        host = dict(zip(METADATA, range(3,12)))
        host.update(profileHex="11"*216, primitivesHex="22"*11)
        self.assertEqual(len(native),256)
        self.assertEqual(host_result_bytes(host), native)
