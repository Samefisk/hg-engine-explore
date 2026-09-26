"""Fake-memory bridge controls, not live actor proof."""
from copy import deepcopy
from types import SimpleNamespace
import struct
import unittest

from tools.overworld.devtools_actor_inspect_probe import ActorInspectProbe, ActorInspectProbeError, BUFFER_BYTES


class Session:
    def __init__(self):
        self.rt = SimpleNamespace(EXECUTED_FRAME_COUNT=100, ACTOR_DESCRIPTOR={
            "facade": dict(version=2),
            "state": dict(address=0x02010000, size=2448, actorStride=172,
                          offsets=dict(actors=68, fieldEpoch=12, mapGeneration=46)),
            "capacities": dict(actors=10),
            "structures": dict(query=24, snapshot=176, actorState=88)})
        self.emu = object()
        self.native_heap_generation = 1
        self.completed_frames = 20
        self.native_allocations = {}
        self.memory = {}
        self.writes = []
        self.field = 0x02020000
        self.service = dict(authenticated=True)
        self.actor = dict(identityVerified=True, handle=dict(slot=7, generation=65535,
            fieldEpoch=2, mapGeneration=3, encounterGeneration=4), subjectIdentity=99,
            species=155, form=0, level=5, role="FOLLOWER")
        self.actor.update(authorityGeneration=1, engineAnchorGeneration=1, presentationGeneration=1,
                          sourceIdentity=dict(object=0x02050000),
                          engineIdentity=dict(pointer=0x02050000, manager_index=5, current_manager=0x02060000,
                              object_manager=0x02060000, object_id=231, object_map_id=33,
                              current_map_id=33, script_id=2074, encounter_generation=4))
        raw = bytearray(88)
        struct.pack_into("<HH6HI", raw, 0, 2, 88, 7, 65535, 2, 3, 4, 0, 99)
        raw[84] = 1
        self.put(0x02010000, bytes(2448))
        self.put(0x02010000, struct.pack("<IHH", 0x5353574F, 2, 2448))
        self.put(0x0201000c, struct.pack("<H", 2))
        self.put(0x0201002e, struct.pack("<H", 3))
        self.actor_address = 0x02010000 + 68 + 7 * 172
        self.put(self.actor_address, raw)

    def field_pointer(self): return self.field
    def _actor_inspect_probe_service(self): return deepcopy(self.service)
    def _snapshot(self, *args, **kwargs): return dict(actors=[deepcopy(self.actor)])
    def put(self, address, data): self.memory.update({address + i: v for i, v in enumerate(data)})
    def read(self, address, size): return bytes(self.memory.get(address + i, 0) for i in range(size))
    def write(self, address, data): self.writes.append((address, len(data))); self.put(address, data)


class ActorInspectProbeTests(unittest.TestCase):
    def fixture(self):
        s = Session()
        return s, ActorInspectProbe(s, expected_actor=s.actor, service_identity=s.service)

    def drive(self, s, p, fault=None):
        g = p.recipe(None, lambda name, args: (name, args))
        self.assertEqual(next(g), ("allocate_work_memory", (11, BUFFER_BYTES)))
        pending = g.send(0x02040000)
        count = 0
        while True:
            name, args = pending
            if name == "free":
                if fault == "free": g.throw(RuntimeError("free failed"))
                try: g.send(0)
                except StopIteration as done: return done.value
            self.assertEqual(name, "inspect_actor")
            self.assertEqual(args, (0x02040010, 0x02040028))
            count += 1
            output = bytearray(176)
            struct.pack_into("<HH4B", output, 0, 1, 176, 1, int(count == 1), 0, 0)
            if count == 1: output[20:108] = s.read(s.actor_address, 88)
            else: self.assertEqual(struct.unpack_from("<H", s.read(args[0], 24), 10)[0], 1)
            s.put(args[1], output)
            if fault == "guard": s.put(0x02040000, b"!")
            if fault == "query": s.put(args[0], b"!")
            if fault == "output": s.put(args[1] + 20, b"!")
            if fault == "actor": s.put(s.actor_address + 24, b"!")
            if fault == "owner": s.native_heap_generation += 1
            if fault == "service": s.service["changed"] = True
            if fault == "uninitialized": s.put(0x02010000, bytes(8))
            if fault == "identity": s.actor["subjectIdentity"] += 1
            s.rt.EXECUTED_FRAME_COUNT += 1
            pending = g.send((0 if count == 1 else 2) if fault != "status" else 1)

    def test_exact_current_and_stale_generation_owned_writes(self):
        s, p = self.fixture()
        result = self.drive(s, p)
        self.assertTrue(result["completed"])
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(s.writes, [(0x02040000, 232)] * 2)
        self.assertEqual(s.native_allocations, {})
        self.assertEqual([r["status"] for r in result["receipts"]], [0, 2])
        for receipt in result["receipts"]:
            self.assertEqual(receipt["currentActorHex"], receipt["currentActorAfterHex"])
            self.assertEqual(receipt["stateBeforeSha256"], receipt["stateAfterSha256"])
        result["receipts"].clear()
        self.assertEqual(len(p.receipts), 2)
        with self.assertRaisesRegex(ActorInspectProbeError, "one-shot"):
            next(p.recipe(None, lambda *args: args))

    def test_faults_free_and_never_complete(self):
        for fault in ("guard", "query", "output", "actor", "identity", "status"):
            with self.subTest(fault=fault):
                s, p = self.fixture()
                with self.assertRaises(ActorInspectProbeError): self.drive(s, p, fault)
                self.assertTrue(p.released)
                self.assertFalse(p.result()["completed"])

    def test_owner_or_auth_loss_refuses_free_and_is_fatal(self):
        for fault in ("owner", "service", "uninitialized"):
            with self.subTest(fault=fault):
                s, p = self.fixture()
                with self.assertRaises(ActorInspectProbeError) as caught: self.drive(s, p, fault)
                self.assertTrue(caught.exception.fatal)
                self.assertFalse(p.released)
                self.assertIn(0x02040000, s.native_allocations)

    def test_free_failure_and_allocation_failure(self):
        s, p = self.fixture()
        with self.assertRaises(RuntimeError): self.drive(s, p, "free")
        self.assertFalse(p.result()["completed"])
        s, p = self.fixture()
        g = p.recipe(None, lambda *args: args)
        next(g)
        with self.assertRaises(ActorInspectProbeError): g.send(0)
        self.assertEqual(s.writes, [])

    def test_selection_occurs_after_allocation_and_rejects_stale_identity(self):
        s, p = self.fixture()
        g = p.recipe(None, lambda *args: args)
        next(g)
        s.actor["subjectIdentity"] += 1
        self.assertEqual(g.send(0x02040000), ("free", (0x02040000,)))
        with self.assertRaises(ActorInspectProbeError): g.send(0)
        self.assertEqual(s.writes, [])

    def test_bound_generations_and_engine_owner_rechecked_after_allocate(self):
        for fault in ("authorityGeneration", "engineAnchorGeneration", "presentationGeneration", "pointer"):
            with self.subTest(fault=fault):
                s, p = self.fixture()
                g = p.recipe(None, lambda *args: args)
                next(g)
                if fault == "pointer":
                    s.actor["sourceIdentity"]["object"] += 300
                    s.actor["engineIdentity"]["pointer"] += 300
                else: s.actor[fault] += 1
                self.assertEqual(g.send(0x02040000), ("free", (0x02040000,)))
                with self.assertRaises(ActorInspectProbeError): g.send(0)
                self.assertEqual(s.writes, [])

    def test_invalid_layout_and_partial_read_fail(self):
        s = Session()
        s.rt.ACTOR_DESCRIPTOR["state"]["actorStride"] = 65536
        with self.assertRaises(ActorInspectProbeError):
            ActorInspectProbe(s, expected_actor=s.actor, service_identity=s.service)
        s, p = self.fixture()
        read = s.read
        s.read = lambda address, size: read(address, size)[:-1] if size == 88 else read(address, size)
        with self.assertRaises(ActorInspectProbeError): self.drive(s, p)
        self.assertTrue(p.released)
