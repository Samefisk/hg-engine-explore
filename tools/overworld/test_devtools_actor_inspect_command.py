"""The native facade probe has one checked subject, never arbitrary calls."""
from copy import deepcopy
import struct
from types import SimpleNamespace
import unittest

from tools.overworld import test_devtools as fixtures
from tools.overworld.devtools_contract import validate_command
from tools.overworld.devtools_records import validate_recipe
from tools.overworld.devtools_runtime import DevtoolsSession, DevtoolsFailure


class ActorInspectCommandTests(unittest.TestCase):
    def test_requires_one_handle_and_no_addresses(self):
        args = {"handle": 65543}
        self.assertEqual(validate_command("actor-inspect.probe", args), args)
        for bad in ({}, {"handle": True}, {"handle": 0}, {"handle": 1 << 32},
                    {**args, "address": 0x02000000}):
            with self.subTest(args=bad), self.assertRaises(ValueError):
                validate_command("actor-inspect.probe", bad)
        recipe = {"schemaVersion": 1, "mode": "prepared",
                  "actions": [{"op": "actor-inspect.probe", "args": args}]}
        self.assertEqual(validate_recipe(recipe), recipe)
        with self.assertRaises(ValueError):
            validate_recipe({**recipe, "mode": "normal"})

    def test_shared_service_retains_receipt_and_marks_prepared(self):
        f = fixtures.ServiceTests(); f.setUp()
        try:
            f.start()
            original = f.service.worker.call
            def call(op, args=None):
                snapshot = original(op, args)
                return {"snapshot": snapshot, "value": {"receipts": ["current", "stale"]},
                        "acceptedProof": False, "setupBoundary": {"eventsDrained": True}}
            f.service.worker.call = call
            receipt = f.service.tests._command("actor-inspect.probe", {"handle": 65543})
            self.assertEqual(receipt["value"]["receipts"], ["current", "stale"])
            self.assertFalse(receipt["acceptedProof"])
            self.assertEqual(f.service.session["mode"], "prepared")
            self.assertEqual(f.service.session["setupMutations"][-1]["op"], "actor-inspect.probe")
        finally:
            f.tearDown(); f.doCleanups()


class ActorInspectAuthTests(unittest.TestCase):
    def fixture(self):
        session = DevtoolsSession.__new__(DevtoolsSession)
        facade = {"address": 0x02300000, "version": 1, "size": 24,
                  "callbacks": dict(validate=0x02300101, apply=0x02300201,
                                    tick=0x02300301, inspect=0x02300401)}
        state = {"address": 0x02200000, "size": 2400}
        session.rt = SimpleNamespace(ACTOR_DESCRIPTOR={"facade": deepcopy(facade), "state": state})
        header = struct.pack("<IHH4I", 0x5341574F, 1, 24, *facade["callbacks"].values())
        memory = {facade["address"]: header, 0x02300400: b"C" * 32,
                  state["address"]: struct.pack("<IHH", 0x5353574F, 1, 2400)}
        session.packaged_code = lambda address, size: memory[address][:size]
        session.read = lambda address, size: memory[address][:size]
        session.target = lambda name: 0x02300400 if name == "inspect_actor" else self.fail(name)
        return session, memory

    def test_authenticates_full_facade_and_initialized_state(self):
        session, memory = self.fixture()
        result = session._actor_inspect_probe_service()
        self.assertEqual(result["inspectAddress"], 0x02300401)
        self.assertEqual(result["facadeHex"], memory[0x02300000].hex())
        for address in (0x02300000, 0x02200000):
            original = memory[address]
            for offset in range(len(original)):
                changed = bytearray(original); changed[offset] ^= 1
                memory[address] = bytes(changed)
                with self.subTest(address=address, offset=offset), self.assertRaises(DevtoolsFailure):
                    session._actor_inspect_probe_service()
            memory[address] = original

    def test_descriptor_cannot_redirect_the_call(self):
        session, _ = self.fixture()
        session.rt.ACTOR_DESCRIPTOR["facade"]["callbacks"]["inspect"] += 4
        with self.assertRaises(DevtoolsFailure): session._actor_inspect_probe_service()

    def test_runtime_rejects_missing_unverified_or_duplicate_subject_before_bridge(self):
        session, _ = self.fixture()
        session.require_quiescent = lambda: None
        session.bridge = SimpleNamespace(run=lambda recipe: self.fail("native call reached"))
        actor = {"handle": {"value": 65543}, "identityVerified": True}
        for actors in ([], [{**actor, "identityVerified": False}], [actor, actor],
                       [{**actor, "handle": {"value": 131079}}]):
            session._snapshot = lambda *args, **kwargs: {"actors": actors}
            with self.subTest(actors=actors), self.assertRaises(DevtoolsFailure) as caught:
                session.actor_inspect_probe({"handle": 65543})
            self.assertEqual(caught.exception.code, "actor-inspect-subject-missing")
            self.assertTrue(session.prepared)


if __name__ == "__main__":
    unittest.main()
