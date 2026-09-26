"""Routing parity: no accepted proof is created by this adapter table."""
from importlib import import_module
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from tools.overworld.proof_adapters import ADAPTERS,ProofAdapter,get_adapter


class ProofAdapterTests(unittest.TestCase):
    def test_native_presentation_level_is_explicit_not_downgraded(self):
        self.assertEqual(ProofAdapter('a','b','c',None).proof_level,'S3')
        self.assertEqual(ProofAdapter('a','b','c','reader','S4').proof_level,'S4')

    def test_exact_adapters_preserve_contracts_faults_and_constructors(self):
        self.assertEqual(len(ADAPTERS),20)
        for kind,adapter in ADAPTERS.items():
            with self.subTest(kind=kind):
                module=import_module('tools.overworld.'+adapter.module_name)
                self.assertIs(get_adapter(kind),adapter)
                if adapter.feature is None:
                    self.assertEqual(adapter.requirement,module.REQUIREMENT)
                    self.assertEqual(adapter.claims,tuple(module.CLAIMS))
                    self.assertEqual(adapter.contract(),module.contract())
                    self.assertEqual(adapter.faults,tuple(module.FAULTS))
                else:
                    self.assertEqual(adapter.requirement,module.requirement(adapter.feature))
                    self.assertEqual(adapter.claims,tuple(module.claims(adapter.feature)))
                    self.assertEqual(adapter.contract(),module.contract(adapter.feature))
                    self.assertEqual(adapter.faults,tuple(module.faults(adapter.feature)))
                self.assertEqual(adapter.proof_level,'S4' if kind in
                                 ('mounted-crash-v1','mount-detach-follower-resume-v1',
                                  'mounted-speed-slew-v1','turn-skid-v1',
                                  'fly-in-runtime-v1','waddle-runtime-v1',
                                  'floaty-bounce-hop-pause-v1') else 'S3')
                for fault in adapter.faults:
                    self.assertIsInstance(adapter.negative(fault),getattr(module,adapter.negative_name))
                with self.assertRaises(ValueError):adapter.negative('unknown-copied-fault')
                if adapter.is_control:
                    self.assertTrue(adapter.requirement.startswith('shared.'))
                elif adapter.recorder_control_requirement is not None:
                    controls=[a for a in ADAPTERS.values() if a.requirement==adapter.recorder_control_requirement]
                    self.assertEqual(len(controls),1);self.assertTrue(controls[0].is_control)

    def test_import_and_lookup_do_not_load_feature_modules(self):
        source='''import json,sys
from tools.overworld.proof_adapters import get_adapter
get_adapter('mounted-stomp-v1')
print(json.dumps(sorted(n for n in sys.modules if n.startswith('tools.overworld.devtools_'))))
'''
        run=subprocess.run([sys.executable,'-c',source],capture_output=True,text=True,timeout=20)
        self.assertEqual(run.returncode,0,run.stderr)
        self.assertEqual(json.loads(run.stdout),[])

    def test_unknown_kind_falls_through_and_table_is_immutable(self):
        for kind in (None,{},'unknown','mounted-frame-pacing-v1'):
            self.assertIsNone(get_adapter(kind))
        with self.assertRaises(TypeError):ADAPTERS['other']=get_adapter('mounted-stomp-v1')

    def test_measurement_and_negative_validation_delegate_without_rewriting(self):
        for adapter in ADAPTERS.values():
            module=adapter.module;replay=object();record=object();result=object()
            with patch.object(module,'measurements',return_value=result) as called:
                self.assertIs(adapter.measurements(replay,record),result)
                called.assert_called_once_with(*((replay,record) if adapter.feature is None
                                                else (adapter.feature,replay,record)))
            with patch.object(module,'validate_negative_result',return_value=result) as called:
                self.assertIs(adapter.validate_negative_result(replay,adapter.faults[0]),result)
                called.assert_called_once_with(*((replay,adapter.faults[0]) if adapter.feature is None
                                                else (adapter.feature,replay,adapter.faults[0])))

    def test_existing_stream_replay_and_exact_named_failure_still_work(self):
        from tools.overworld.test_devtools_stomp_measurement import raw_records
        from tools.overworld.devtools_stomp_proof import replay_records
        test,rows=raw_records();adapter=get_adapter('mounted-stomp-v1')
        baseline=replay_records(test,rows)
        record=dict(sessionId='host',sessionCleanup=dict(sessionId='host',closed=True,errors=[]))
        self.assertEqual(len(adapter.measurements(baseline,record)),6)
        fault='stomp-missing-dust'
        adapter.validate_negative_result(replay_records(test,rows,fault=fault),fault)
        self.assertFalse(baseline['measurements'][adapter.kind]['acceptedProof'])


if __name__=='__main__':unittest.main()
