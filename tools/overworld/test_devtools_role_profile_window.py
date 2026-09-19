"""Prepared recording-window controls using the real role-profile lifetime."""
from contextlib import contextmanager
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_runtime import DevtoolsSession, DevtoolsFailure
from tools.overworld import test_devtools_role_profile as role_fixtures


class RoleProfileWindowTests(unittest.TestCase):
    def fixture(self):
        reader, old, actor, source, engine, regs, put, calls = role_fixtures.RoleProfileTests().fixture()
        session = DevtoolsSession.__new__(DevtoolsSession)
        session.__dict__.update(old.__dict__)
        session.native_observation = reader.observer
        session.native_observation.role_profiles = reader
        reader.session = reader.observer.session = session
        session.native_observation.binding_context = SimpleNamespace(enable=lambda: None)
        session.semantic_trace = session.sampling_hook = session.party_getter_hooks = None
        session.observer_control = session.route_control = None
        session.closed = False
        log = []
        session.emu.destroy = lambda: log.append("destroy")
        session.rt.h = SimpleNamespace(set_key_mask=lambda *args: log.append("keys-release"))
        session.native_observation.close = lambda: log.append("observer-close")
        def boundary(operation, frames=None):
            log.append(operation)
            if operation == "start": self.assertFalse(reader.active)
            if operation == "stop": self.assertTrue(reader.active)
            return {"recording": operation == "start"}
        session._record_control = boundary
        original = reader.capture
        @contextmanager
        def capture(*, control=False):
            self.assertIs(control, False)
            log.append("enter")
            try:
                with original(control=control): yield reader
            finally: log.append("exit")
        reader.capture = capture
        return session, reader, log, calls

    def test_after_boundary_start_and_stop_cleanup_no_control_mutation(self):
        s,r,log,calls=self.fixture()
        self.assertTrue(s.record_start(10,role_profile=True)["recording"])
        self.assertEqual(log,["start","enter"])
        self.assertTrue(r.active);self.assertFalse(r.control)
        self.assertFalse(s.record_stop()["recording"])
        self.assertEqual(log,["start","enter","stop","exit"])
        self.assertFalse(r.active);self.assertEqual(r.observer.tokens,[])
        s.close();s.close()
        self.assertEqual(log.count("exit"),1);self.assertEqual(log.count("destroy"),1)

    def test_default_has_no_capture_hooks(self):
        s,r,log,calls=self.fixture();s.record_start(10)
        self.assertEqual(log,["start"]);self.assertFalse(r.active);self.assertEqual(calls,[])

    def test_prepared_boolean_and_duplicate_validation_happen_before_boundary(self):
        for bad in (1,None,"yes"):
            s,r,log,_=self.fixture()
            with self.subTest(bad=bad),self.assertRaises(DevtoolsFailure):s.record_start(10,role_profile=bad)
            self.assertEqual(log,[])
        s,r,log,_=self.fixture();s.prepared=False
        with self.assertRaises(DevtoolsFailure):s.record_start(10,role_profile=True)
        self.assertEqual(log,[])
        s,r,log,_=self.fixture();s.record_start(10,role_profile=True)
        with self.assertRaises(DevtoolsFailure):s.record_start(10,role_profile=True)
        self.assertEqual(log,["start","enter"]);s.close()

    def test_failed_start_boundary_does_not_enter_capture(self):
        s,r,log,_=self.fixture()
        def fail(*args):raise RuntimeError("boundary failed")
        s._record_control=fail
        with self.assertRaisesRegex(RuntimeError,"boundary failed"):s.record_start(10,role_profile=True)
        self.assertFalse(r.active);self.assertEqual(log,[])

    def test_failed_hook_install_leaves_no_window(self):
        s,r,log,_=self.fixture()
        r._install_tap=lambda *args,**kwargs:(_ for _ in ()).throw(ValueError("install failed"))
        with self.assertRaisesRegex(ValueError,"install failed"):
            s.record_start(10,role_profile=True)
        self.assertEqual(log,["start","enter","exit"])
        self.assertFalse(r.active);self.assertEqual(r.observer.tokens,[])
        self.assertIsNone(getattr(s,"_role_profile_window",None))
        s.close();self.assertEqual(log.count("exit"),1)

    def test_worker_forwards_explicit_opt_in_and_default(self):
        path=Path(__file__).resolve().parents[2]/"scripts/overworld_devtools_worker.py"
        tree=ast.parse(path.read_text())
        branch=next(node for node in ast.walk(tree) if isinstance(node,ast.If)
                    and ast.unparse(node.test)=="operation == 'record.start'")
        code=compile(ast.fix_missing_locations(ast.Module(body=branch.body,type_ignores=[])),str(path),"exec")
        for args in ({},{"maxFrames":10,"roleProfile":True}):
            s,r,log,_=self.fixture()
            exec(code,{"session":s,"args":args})
            self.assertEqual(r.active,args.get("roleProfile",False))
            s.close()

    def test_unrelated_tap_installed_midwindow_survives_stop(self):
        s,r,log,_=self.fixture();s.record_start(10,role_profile=True)
        observer=r.observer
        calls=[]
        token=observer.hooks.add(0x02300000,lambda:calls.append("unrelated"))
        observer.tokens.append(token)
        pending={"data":{"unrelated":True}}
        observer.contexts.append(pending)
        return_token=observer.hooks.add(0x02300080,lambda:None)
        observer.return_tokens.append(return_token)
        s.record_stop()
        self.assertEqual(observer.tokens,[token])
        self.assertEqual(observer.return_tokens,[return_token])
        self.assertEqual(observer.contexts,[pending])
        self.assertIn(token[1],observer.hooks.callbacks[token[0]])
        token[1]();self.assertEqual(calls,["unrelated"])
        s.close()

    def test_stop_failure_still_closes_and_preserves_first_error(self):
        s,r,log,_=self.fixture();s.record_start(10,role_profile=True)
        original=RuntimeError("stop failed")
        def fail(*args):raise original
        s._record_control=fail
        r.observer.hooks.retire_empty=lambda addr:(_ for _ in ()).throw(ValueError("retire failed"))
        with self.assertRaises(RuntimeError) as caught:s.record_stop()
        self.assertIs(caught.exception,original);self.assertFalse(r.active)
        self.assertTrue(original.role_profile_cleanup_errors)
        s.close();self.assertEqual(log.count("exit"),1)

    def test_close_removes_window_before_general_observer_and_on_error(self):
        s,r,log,_=self.fixture();s.record_start(10,role_profile=True);s.close()
        self.assertLess(log.index("exit"),log.index("observer-close"));self.assertTrue(s.closed)
        s,r,log,_=self.fixture();s.record_start(10,role_profile=True)
        r.observer.hooks.retire_empty=lambda addr:(_ for _ in ()).throw(ValueError("retire failed"))
        with self.assertRaisesRegex(ValueError,"cleanup failed"):s.close()
        self.assertIsNone(s.emu);self.assertTrue(s.closed);self.assertFalse(r.active)
        s.close();self.assertEqual(log.count("exit"),1);self.assertEqual(log.count("destroy"),1)


if __name__ == "__main__": unittest.main()
