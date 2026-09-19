"""Retire only empty setup IRQ taps, with no emulator or native stepping."""
import ast
from copy import deepcopy
import json
from tools.overworld.devtools_evidence_stream import load_observations
from pathlib import Path
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_runtime import DevtoolsHooks, DevtoolsSession, DevtoolsFailure
from tools.overworld import test_devtools_jobs as job_fixtures

IRQ = (0x01FF8000,0x01FF804C,0x01FF80B4,0x01FF80B8,0x01FF80F4,
       0x01FF8120,0x01FF8178,0x01FF8188,0x01FF81A0)


class ObservationPrepareTests(unittest.TestCase):
    def fixture(self):
        calls=[]
        emu=SimpleNamespace(memory=SimpleNamespace(register_exec=lambda address, callback: calls.append((address,callback))))
        rt=SimpleNamespace(EXECUTED_FRAME_COUNT=40)
        session=DevtoolsSession.__new__(DevtoolsSession)
        session.emu,session.rt,session.completed_frames=emu,rt,20
        session.native_bridge_active=session.native_trampoline_in_use=session.native_health_exclusion_active=False
        session.party_getter_hooks=DevtoolsHooks(rt,emu)
        return session,calls

    def test_only_empty_setup_irq_dispatchers_are_retired_once_and_can_readd(self):
        session,calls=self.fixture();hooks=session.party_getter_hooks
        tokens=[hooks.add(a,lambda:None) for a in IRQ]
        unrelated=hooks.add(0x02001000,lambda:None);hooks.remove(unrelated)
        for token in tokens[:-1]:hooks.remove(token)
        before=len(calls)
        receipt=session.prepare_observation()
        self.assertIs(receipt["onePassPerCore"],True)
        self.assertEqual(receipt["advancedFrames"],0)
        self.assertEqual((session.completed_frames,session.rt.EXECUTED_FRAME_COUNT),(20,40))
        self.assertEqual([address for address,callback in calls[before:] if callback is None],list(IRQ[:-1]))
        self.assertEqual([r["address"] for r in receipt["removed"]],list(IRQ[:-1]))
        self.assertEqual(receipt["retained"],[{"name":"irq-return-thread-switch","address":IRQ[-1],"reason":"active-listeners"}])
        self.assertIn(0x02001000,hooks.callbacks)
        self.assertIn(IRQ[-1],hooks.callbacks)
        original=deepcopy(receipt)
        hooks.add(IRQ[0],lambda:None)
        self.assertIsNotNone(calls[-1][1])
        count=len(calls)
        receipt["removed"].clear()
        self.assertEqual(session.prepare_observation(),original)
        self.assertEqual(len(calls),count)
        self.assertIn(IRQ[0],hooks.callbacks)

    def test_unregister_failure_retains_cache_and_cannot_repeat_partial_pass(self):
        session,calls=self.fixture();hooks=session.party_getter_hooks
        token=hooks.add(IRQ[0],lambda:None);hooks.remove(token)
        def fail(address,callback):
            calls.append((address,callback))
            raise RuntimeError("unregister failed")
        session.emu.memory.register_exec=fail
        with self.assertRaises(DevtoolsFailure):session.prepare_observation()
        self.assertIn(IRQ[0],hooks.callbacks)
        count=len(calls)
        with self.assertRaises(DevtoolsFailure):session.prepare_observation()
        self.assertEqual(len(calls),count)

    def test_all_nine_readded_callbacks_cannot_be_retired_again(self):
        session,calls=self.fixture();hooks=session.party_getter_hooks
        for address in IRQ:
            token=hooks.add(address,lambda:None);hooks.remove(token)
        session.prepare_observation()
        for address in IRQ:
            token=hooks.add(address,lambda:None);hooks.remove(token)
        count=len(calls)
        session.prepare_observation()
        self.assertEqual(len(calls),count)
        self.assertEqual(sum(callback is not None for _,callback in calls),18)
        self.assertEqual(sum(callback is None for _,callback in calls),9)

    def test_active_bridge_trampoline_and_closed_core_reject_before_retirement(self):
        for flag in ("native_bridge_active","native_trampoline_in_use","native_health_exclusion_active","closed"):
            session,calls=self.fixture()
            if flag=="closed":session.emu=None
            else:setattr(session,flag,True)
            with self.assertRaises(DevtoolsFailure):session.prepare_observation()
            self.assertEqual(calls,[])

    def test_worker_internal_operation_calls_real_prepare_without_other_work(self):
        path=Path(__file__).resolve().parents[2]/"scripts/overworld_devtools_worker.py"
        tree=ast.parse(path.read_text())
        branch=next(n for n in ast.walk(tree) if isinstance(n,ast.If)
                    and ast.unparse(n.test)=="operation == 'observation.prepare'")
        session,calls=self.fixture()
        scope={"session":session,"args":{}}
        exec(compile(ast.fix_missing_locations(ast.Module(body=branch.body,type_ignores=[])),str(path),"exec"),scope)
        self.assertEqual(scope["result"]["frame"],20)
        self.assertEqual(scope["result"]["nativeCycle"],40)
        self.assertEqual(calls,[])

    def test_job_prepares_once_under_lock_before_observe_for_both_record_start_paths(self):
        for mode in ("normal","prepared"):
            with self.subTest(mode=mode):
                fixture=job_fixtures.JobsTests();fixture.setUp()
                try:
                    class Worker(job_fixtures.FrameWorker):
                        def call(self,op,args=None):
                            if op=="observation.prepare":
                                self.calls.append((op,args))
                                if not fixture.service.lock._is_owned():raise AssertionError("prepare was not locked")
                                return {"frame":self.frame,"nativeCycle":self.frame*2,"removed":[],"retained":[]}
                            return super().call(op,args)
                    fixture.service.worker_factory=Worker
                    value=job_fixtures.recipe();value["mode"]=mode
                    self.assertTrue(fixture.launch(value)["ok"])
                    result=fixture.finish()
                    self.assertTrue(result["passed"],result)
                    worker=Worker.instances[-1]
                    ops=[op for op,args in worker.calls]
                    self.assertEqual(ops.count("observation.prepare"),1)
                    self.assertLess(ops.index("observation.prepare"),ops.index("step"))
                    manifest=json.loads(Path(result["manifest"]).read_text())
                    self.assertEqual(manifest["observationSetup"]["frame"],1)
                    rows=load_observations(Path(manifest["observationsArtifact"]["path"]))
                    self.assertFalse(any(row.get("command") == "observation.prepare" for row in rows))
                finally:
                    fixture.tearDown();fixture.doCleanups()


if __name__=="__main__":unittest.main()
