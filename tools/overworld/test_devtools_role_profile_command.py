"""Opt-in profile reads never burden unrelated prepared movement fixtures."""
from contextlib import contextmanager
from types import SimpleNamespace as NS
import unittest

from tools.overworld.devtools_contract import validate_command
from tools.overworld.devtools_runtime import DevtoolsSession, DevtoolsFailure


class ProfileCommandTests(unittest.TestCase):
    def test_contract_only_accepts_named_follower_mount_diagnostic(self):
        for role in ("follower", "mounted"):
            value = validate_command("spawn", dict(species=155, role=role,
                profileDiagnostics="owner-transfer"))
            self.assertEqual(value["profileDiagnostics"], "owner-transfer")
        self.assertNotIn("profileDiagnostics", validate_command("spawn", dict(species=165)))
        self.assertEqual(validate_command("spawn", dict(species=56,role="mounted",
            profileDiagnostics="owner-transfer-control"))["profileDiagnostics"],"owner-transfer-control")
        for role, value in (("wild", "owner-transfer"), ("follower", True),
                            ("mounted", "all"), ("mounted", None), ("follower", "owner-transfer-control")):
            with self.assertRaises(ValueError):
                validate_command("spawn", dict(species=155, role=role, profileDiagnostics=value))

    def test_capture_brackets_only_opted_in_lifecycle_and_exits_before_boundary(self):
        calls = []
        getter = dict(kind="native-observation", frame=8, data=dict(observation="role-profile-getter"))
        mounted = dict(kind="native-observation", frame=8, data=dict(observation="role-profile-mount"))
        @contextmanager
        def capture(control=False):
            if control: calls.append("control")
            calls.append("enter")
            try: yield
            finally: calls.append("exit")
        session = NS(prepared=False, party_snapshot=lambda: [dict(species=155,isEgg=False,hp=20)],
            native_observation=NS(role_profiles=NS(capture=capture)),
            _spawn_party_subject=lambda *a, **k: calls.append("spawn") or {},
            _prepared_result_boundary=lambda v: calls.append("boundary") or
                {**v,"events":[getter,mounted,dict(kind="unrelated")]})
        args = dict(species=155,role="mounted",slot=0)
        DevtoolsSession.spawn(session,args)
        self.assertEqual(calls,["spawn","boundary"])
        calls.clear()
        result = DevtoolsSession.spawn(session,{**args,"profileDiagnostics":"owner-transfer"})
        self.assertEqual(calls,["enter","spawn","exit","boundary"])
        self.assertEqual(result["profileDiagnostics"],"owner-transfer")
        self.assertEqual(result["profileObservation"]["events"],[getter,mounted])
        self.assertFalse(result["profileObservation"]["acceptedProof"])
        calls.clear()
        result = DevtoolsSession.spawn(session,{**args,"profileDiagnostics":"owner-transfer-control"})
        self.assertEqual(calls,["control","enter","spawn","exit","boundary"])
        self.assertIn("calibration only",result["profileObservation"]["scope"])
        session.prepared = False
        with self.assertRaises(DevtoolsFailure):
            DevtoolsSession.spawn(session,dict(species=165,profileDiagnostics="owner-transfer"))
        self.assertFalse(session.prepared)


if __name__ == "__main__": unittest.main()
