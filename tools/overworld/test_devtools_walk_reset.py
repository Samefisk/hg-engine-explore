"""Host controls for the real RESET recipe; no game execution."""
from copy import deepcopy
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.overworld.devtools_walk_reset import WalkPolicyReset, WalkResetError
from tools.overworld.devtools_records import select_current_actor


class Session:
    def __init__(self, role="WILD"):
        self.rt = SimpleNamespace(ACTOR_DESCRIPTOR={
            "facade": dict(version=2),
            "state": dict(address=0x02010000, size=2448, actorStride=172,
                          actorPolicyOffset=140, offsets=dict(actors=68)),
            "structures": dict(actorPolicyState=32),
            "capacities": dict(actors=10), "privateServices": [dict(name="movementPolicy", status="available",
                version=5, size=16, conditionAdapter=0x02030300,
                address=0x02030000, policy=0x02030100)]})
        self.native_trampoline = {"address": 0x02040000}
        self.native_heap_generation = 1
        self.emu = object()
        self.memory, self.writes = {}, []
        self.put(0x02010000, bytes(2448))
        self.put(0x02010000, struct.pack("<IHH", 0x5353574F, 2, 2448))
        self.slot = 7 if role == "MOUNTED" else 0
        self.policy_address = 0x02010000 + 68 + self.slot * 172 + 140
        policy = bytearray(range(32))
        policy[5] = policy[22] = policy[23] = 0
        self.put(self.policy_address, policy)
        self.pose = dict(flags=1, x=2, y=3, pos_x=(2 << 16) + 0x8000,
                         pos_z=(3 << 16) + 0x8000, pos_y=0, movement_cmd=0)
        self.actor = dict(active=True, identityVerified=True, presentationAttached=True,
            handle=dict(value=65536 | self.slot, slot=self.slot, generation=1, fieldEpoch=2,
                        mapGeneration=3, encounterGeneration=4), subjectIdentity=99, species=165,
            role=role, form=0, level=5, authorityGeneration=1, engineAnchorGeneration=1,
            presentationGeneration=1, engineIdentity=dict(pointer=0x02050000, anchorPointer=0x02060000),
            sourceIdentity=dict(object=0x02050000), engineObject=deepcopy(self.pose),
            stagedMovement=dict(known=True, idle=True),
            motionPhase="IDLE", reservationId=0, inputOwnership=int(role == "MOUNTED"),
            behaviorFingerprint=123, matchedLayerMask=456)
        self.rt.wild_staged_motion = lambda _emu, _slot: deepcopy(self.actor.get("stagedMovement"))
        self.actor["stagedMovement"].update(slot=self.slot, objectPointer=0x02050000)
        self.inputs = dict.fromkeys(("state", "heldKeys", "newKeys", "rawHeld", "rawNew", "simulatedKeys", "physicalPressed"), 0)
        self.table = struct.pack("<6I", 1, 3, 5, 0x02030201, 7, 9)
        self.subject = select_current_actor(self._snapshot(), self.actor)

    def field_pointer(self): return 0x02020000
    def target(self, name):
        assert name == "reduce_walk"
        return 0x02030200
    def packaged_code(self, address, size):
        return {0x02030000: struct.pack(
                    "<IHHII", 0x504D574F, 5, 16, 0x02030100, 0x02030300),
                0x02030100: self.table, 0x02030200: bytes(32)}[address]
    def require_quiescent(self): pass
    def _snapshot(self, *args, **kwargs):
        return dict(frame=20, nativeCycle=30, context=dict(fieldEpoch=2, mapGeneration=3),
                    actors=[deepcopy(self.actor)], player=deepcopy(self.pose))
    def _selector_observation(self): return deepcopy(self.inputs)
    def put(self, address, data): self.memory.update({address + i: x for i, x in enumerate(data)})
    def read(self, address, size): return bytes(self.memory.get(address + i, 0) for i in range(size))
    def write(self, address, data): self.writes.append((address, len(data))); self.put(address, data)


class WalkResetTests(unittest.TestCase):
    def test_runtime_outer_endpoint_uses_completed_snapshot(self):
        from tools.overworld.devtools_runtime import DevtoolsSession
        completed = dict(frame=2, fieldAvailable=True,
                         observationBoundary="main-task-queue-completion")
        calls = []
        def snapshot(radius, *, diagnostic_details):
            calls.append((radius, diagnostic_details))
            return deepcopy(completed)
        session = SimpleNamespace(prepared=False, snapshot=snapshot,
            bridge=SimpleNamespace(run=lambda recipe: {"value": {"raw": "unchanged"}}),
            _prepared_result_boundary=lambda receipt: receipt)
        with patch("tools.overworld.devtools_walk_reset.WalkPolicyReset",
                   return_value=SimpleNamespace(recipe=lambda *args: None)):
            result = DevtoolsSession.walk_policy_reset(session, {"subject": {}})
        self.assertEqual(result["snapshot"], completed)
        self.assertEqual(result["value"], {"raw": "unchanged"})
        self.assertEqual(calls, [(0, False)])

    def drive(self, session, fault=None):
        reset = WalkPolicyReset(session, session.subject)
        recipe = reset.recipe(0x02040200, lambda name, args: (name, args))
        self.assertEqual(next(recipe), ("reduce_walk", (0x02040210,)))
        request = session.read(0x02040210, 28)
        self.assertEqual(request, struct.pack("<HHI", 1, 28, 0) + bytes((session.slot, 0)) + bytes(18))
        if fault == "core":
            recipe.throw(RuntimeError("core failed"))
        policy = bytearray(session.read(session.policy_address, 32))
        policy[:8] = bytes((255, 0, 0, 0, 255, 0, 0, 0))
        policy[16:19] = bytes(3)
        policy[20:24] = bytes((255, 0, 0, 0))
        if fault == "profile": policy[8] ^= 1
        if fault != "ignored": session.put(session.policy_address, policy)
        if fault == "pose": session.actor["engineObject"]["pos_y"] += 1
        if fault == "anchor": session.pose["pos_y"] += 1
        if fault == "actor": session.actor["authorityGeneration"] += 1
        if fault == "other-state": session.put(0x02010020, b"!")
        try: recipe.send(0 if fault == "return" else 1)
        except StopIteration as done: return done.value

    def test_exact_reset_wild_and_mounted_preserves_profile_pose_and_scratch(self):
        for role in ("WILD", "MOUNTED"):
            with self.subTest(role=role):
                session = Session(role)
                receipt = self.drive(session)
                self.assertTrue(receipt["completed"])
                self.assertFalse(receipt["acceptedProof"])
                self.assertTrue(receipt["prepared"])
                self.assertEqual(receipt["fieldPointer"], session.field_pointer())
                self.assertEqual(receipt["heapGeneration"], session.native_heap_generation)
                self.assertTrue(receipt["scratchRestored"])
                self.assertEqual(session.writes, [(0x02040200, 60)] * 2)
                self.assertEqual(session.read(0x02040200, 60), bytes(60))

    def test_missing_stale_or_busy_subject_stops_before_any_write(self):
        for fault in ("missing", "generation", "engine", "motion", "reservation", "input", "pending", "skid", "object"):
            with self.subTest(fault=fault):
                s = Session()
                if fault == "missing": del s.subject["authorityGeneration"]
                elif fault == "generation": s.actor["authorityGeneration"] += 1
                elif fault == "engine": s.actor["engineIdentity"]["pointer"] += 4
                elif fault == "motion": s.actor["motionPhase"] = "MOVING"
                elif fault == "reservation": s.actor["reservationId"] = 1
                elif fault == "input": s.inputs["heldKeys"] = 16
                elif fault == "pending": s.put(s.policy_address + 22, b"\x03")
                elif fault == "skid": s.put(s.policy_address + 5, b"\x01")
                elif fault == "object": s.actor["engineObject"]["flags"] |= 2
                with self.assertRaises(ValueError): WalkPolicyReset(s, s.subject)
                self.assertEqual(s.writes, [])

    def test_callback_authentication_and_reselection_at_bridge_boundary(self):
        s = Session()
        s.table = bytes(24)
        with self.assertRaisesRegex(WalkResetError, "callback"): WalkPolicyReset(s, s.subject)
        s = Session()
        reset = WalkPolicyReset(s, s.subject)
        s.actor["subjectIdentity"] += 1
        with self.assertRaises(ValueError): next(reset.recipe(0x02040200, lambda *args: args))
        self.assertEqual(s.writes, [])

    def test_unobserved_or_active_staged_state_denies_reset(self):
        for staged in (None, {}, {"known": False}, {"known": True, "idle": False}):
            with self.subTest(staged=staged):
                s = Session()
                s.actor["stagedMovement"] = staged
                with self.assertRaises(WalkResetError) as caught:
                    WalkPolicyReset(s, s.subject)
                if not staged or staged.get("known") is not True:
                    self.assertEqual(caught.exception.code, "walk-reset-staged-state-unavailable")
                self.assertEqual(s.writes, [])

    def test_missing_readiness_preserves_the_native_failure_reason(self):
        s = Session()
        s.actor["stagedMovement"] = {"known": False, "reason": "staged-motion-layout-code-unknown"}
        with self.assertRaisesRegex(WalkResetError, "staged-motion-layout-code-unknown"):
            WalkPolicyReset(s, s.subject)
        self.assertEqual(s.writes, [])

    def test_runtime_taints_failed_preparation_and_rejects_follower(self):
        from tools.overworld.devtools_runtime import DevtoolsSession
        s = Session()
        s.prepared = False
        s.actor["stagedMovement"] = None
        with self.assertRaises(WalkResetError):
            DevtoolsSession.walk_policy_reset(s, {"subject": s.subject})
        self.assertTrue(s.prepared)
        s = Session("FOLLOWER")
        with self.assertRaisesRegex(WalkResetError, "role"):
            WalkPolicyReset(s, s.subject)
        self.assertEqual(s.writes, [])

    def test_failed_return_or_changed_state_never_completes_and_restores_scratch(self):
        for fault in ("core", "return", "ignored", "profile", "pose", "anchor", "actor", "other-state"):
            with self.subTest(fault=fault):
                s = Session()
                with self.assertRaises((ValueError, RuntimeError)): self.drive(s, fault)
                self.assertEqual(s.read(0x02040200, 60), bytes(60))

    def test_public_header_and_native_reset_anchor(self):
        root = Path(__file__).resolve().parents[2]
        header = (root / "include/overworld_wild_movement.h").read_text()
        self.assertIn("OVERWORLD_ACTOR_WALK_POLICY_RESET = 0", header)
        self.assertIn("#define OVERWORLD_ACTOR_WALK_POLICY_VERSION 1", header)
        self.assertIn("sizeof(OverworldActorWalkPolicyCall) == 28", header)
        self.assertIn("#define OW_WILD_WALK_DIRECTION_NONE 0xFF", header)
        internal = (root / "include/overworld_actor_system_internal.h").read_text()
        self.assertIn("sizeof(OverworldActorPolicyState) == 32", internal)
        self.assertIn("reduceWalk at byte offset 12", internal)
        source = (root / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c").read_text()
        self.assertIn("OverworldActorWalkPolicy_ResetState(policy, FALSE, 0, 0);", source)
        body = source.split("static void OverworldActorWalkPolicy_ResetState(", 1)[1].split("/* Several policy", 1)[0]
        for field in ("chainStepsRemaining", "deferredChainPauseTicks", "deferredChainPauseAction"):
            self.assertIn("policy->" + field + " = 0;", body)


if __name__ == "__main__":
    unittest.main()
