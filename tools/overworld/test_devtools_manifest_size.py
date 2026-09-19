"""Manifest writer/reader size contract, without touching retained artifacts."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.overworld import devtools_jobs as jobs


class ManifestSizeTests(unittest.TestCase):
    def test_writer_is_compact_and_preserves_every_field(self):
        value={"nested":{"values":[1,True,None,"æ"],"message":"line\nnext"},"empty":{},"fraction":1.25}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"manifest.json"
            jobs._write(path,value)
            data=path.read_bytes()
            self.assertEqual(json.loads(data),value)
            self.assertEqual(data,(json.dumps(value,separators=(",",":"),allow_nan=False)+"\n").encode("utf-8"))
            self.assertFalse(path.with_suffix(".tmp").exists())

    def test_oversize_control_cannot_publish_acceptance_but_keeps_all_evidence(self):
        evidence={"nativeReceipts":[{"data":"x"*512}],"failures":[]}
        record={"state":"completed","passed":True,"acceptedProof":True,"evaluation":deepcopy(evidence),
                "proofAcceptance":{"eligible":True,"claims":["controlled-action"]}}
        with patch.object(jobs,"MANIFEST_MAX_BYTES",128):
            jobs._guard_manifest_size(record,"observer-control")
        self.assertFalse(record["passed"])
        self.assertFalse(record["acceptedProof"])
        self.assertEqual(record["state"],"failed")
        self.assertEqual(record["evaluation"],evidence)
        self.assertEqual(record["proofAcceptance"]["claims"],["controlled-action"])
        self.assertEqual(record["manifestSizeFailure"]["maximumBytes"],128)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"manifest.json";jobs._write(path,record)
            self.assertEqual(json.loads(path.read_bytes()),record)

    def test_exact_limit_is_allowed_and_one_byte_less_rejects(self):
        original={"state":"completed","passed":True,"acceptedProof":True,"proofAcceptance":{}}
        size=len((json.dumps(original,separators=(",",":"),allow_nan=False)+"\n").encode("utf-8"))
        for limit,accepted in ((size,True),(size-1,False)):
            with self.subTest(limit=limit):
                value=deepcopy(original)
                with patch.object(jobs,"MANIFEST_MAX_BYTES",limit):jobs._guard_manifest_size(value,"observer-control")
                self.assertIs(value["acceptedProof"],accepted)

    def test_guard_does_not_relabel_existing_failures_or_normal_route(self):
        for mode,accepted in (("observer-control",False),("normal",True)):
            value={"acceptedProof":accepted,"passed":accepted,"evaluation":{"data":"x"*512}}
            before=deepcopy(value)
            with patch.object(jobs,"MANIFEST_MAX_BYTES",128):jobs._guard_manifest_size(value,mode)
            self.assertEqual(value,before)

    def test_actual_job_terminal_write_applies_guard_after_acceptance(self):
        # Stub controller approval only to test publication ordering; no native
        # measurement result is invented or treated as gameplay proof here.
        from tools.overworld import test_devtools_jobs as fixtures
        fixture=fixtures.JobsTests();fixture.setUp()
        try:
            value=fixtures.recipe();value["mode"]="observer-control"
            approval={"passed":True,"acceptedProof":True,
                      "proofAcceptance":{"eligible":True,"testEvidence":"x"*512}}
            with patch("tools.overworld.control.finalize_shared_test",return_value=approval), \
                    patch.object(jobs,"MANIFEST_MAX_BYTES",128):
                self.assertTrue(fixture.launch(value)["ok"])
                result=fixture.finish()
            saved=json.loads(Path(result["manifest"]).read_bytes())
            self.assertFalse(result["acceptedProof"])
            self.assertFalse(saved["acceptedProof"])
            self.assertEqual(saved["state"],"failed")
            self.assertEqual(saved["proofAcceptance"]["testEvidence"],"x"*512)
            self.assertTrue(saved["evaluation"]["passed"])
        finally:
            fixture.tearDown();fixture.doCleanups()

    def test_real_retained_5fcada_compacts_losslessly_below_reader_limit(self):
        root=Path(__file__).resolve().parents[2]
        path=root/"build/overworld-devtools/test-5fcada9c0798444c9a92301438349626/manifest.json"
        if not path.is_file():self.skipTest("optional immutable native manifest is absent")
        original_bytes=path.read_bytes()
        value=json.loads(original_bytes)
        compact=(json.dumps(value,separators=(",",":"),allow_nan=False)+"\n").encode("utf-8")
        self.assertGreater(len(original_bytes),8*1024*1024)
        self.assertLessEqual(len(compact),8*1024*1024)
        self.assertEqual(json.loads(compact),value)
        self.assertEqual(path.read_bytes(),original_bytes)


if __name__=="__main__":unittest.main()
