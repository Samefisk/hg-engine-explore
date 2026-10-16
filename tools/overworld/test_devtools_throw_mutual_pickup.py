"""Copied native-shaped controls for the two-Geodude mutual pickup case."""
from copy import deepcopy
import hashlib
import json
import struct
import unittest
from pathlib import Path

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_throw_mutual_pickup_measurement import (
    ThrowMutualPickupMeasurement, KIND, CASE, ACTIONS, validate_recipe,
)
from tools.overworld.devtools_throw_mutual_pickup_proof import (
    FAULTS, ThrowMutualPickupNegative, contract, measurements,
)
from tools.overworld.test_devtools_throw_cargo_competition import binding
from tools.overworld.test_devtools_player_health_throw_contact_measurement import (
    actor, snapshot, step_row, ROM, OVERLAY,
)
from tools.overworld.test_devtools_wild_throw_moving_candidate_measurement import native_motion
from tools.overworld.test_devtools_cargo_route_continuity import query_event, IMAGE
from tools.overworld.devtools_wild_throw_moving_candidate_measurement import THROW_RELEASE_BIT

ROOT = Path(__file__).resolve().parents[2]
SOURCE = dict(contractVersion=2, romSha256=ROM, overlaySha256=OVERLAY,
              profileSha256="c" * 64, queryImage=IMAGE)


def sample(frame):
    s = snapshot(frame)
    s.update(actorFrame=frame)
    s["player"].update(x=586, y=406)
    s["fieldControl"]["fieldPointer"] = 0x2200000
    a, b = actor(74, 0, 740, 402), actor(74, 1, 741, 402)
    for item, x in ((a, 584 if frame <= 1 else 585), (b, 588)):
        item.update(level=20)
        for key in ("logical", "render", "origin", "target"):
            item[key] = dict(x=x, y=402)
        item["engineObject"].update(x=x, y=402,
                                    pos_x=(x << 16) + 32768, pos_z=(402 << 16) + 32768)
        item["sourceIdentity"] = dict(object=item["engineIdentity"]["pointer"],
                                      personality=item["subjectIdentity"], map_id=33,
                                      species=74, form=0, level=20, active=1,
                                      object_id=224 + item["handle"]["slot"],
                                      encounter_generation=1)
    if 1 <= frame <= 3:
        a.update(motionKind="WALK", motionPhase="MOVING", motionDuration=8,
                 motionElapsed=frame, reservationId=8,
                 origin=dict(x=584, y=402), target=dict(x=585, y=402))
    if 2 <= frame <= 3:
        b.update(motionKind="WALK", motionPhase="MOVING", motionDuration=8,
                 motionElapsed=frame - 1, reservationId=9,
                 origin=dict(x=588, y=402), target=dict(x=587, y=402))
    if frame == 7:
        a.update(motionKind="HOP", motionPhase="MOVING", motionDuration=20,
                 motionElapsed=0, reservationId=10,
                 origin=dict(x=585, y=402), target=dict(x=583, y=404))
        b["matchedLayerMask"] = THROW_RELEASE_BIT
    s["actors"] = [a, b]
    targets = [0] * 10
    if 1 <= frame <= 3:
        targets[0] = 2
    if 2 <= frame <= 3:
        targets[1] = 1
    if 4 <= frame <= 6:
        targets[1] = 129
    target_mask = 2 if frame == 1 else 3 if 2 <= frame <= 3 else 1 if 4 <= frame <= 6 else 0
    carrier_mask = 1 if frame == 1 else 3 if 2 <= frame <= 3 else 2 if 4 <= frame <= 6 else 0
    state = dict(targets=targets, targetMask=target_mask, carrierMask=carrier_mask,
                 recoveringMask=0, rawHex=(bytes(targets) + struct.pack(
                     "<3H", target_mask, carrier_mask, 0)).hex())
    rows = []
    for item, target in ((a, b), (b, a)):
        encoded = targets[item["handle"]["slot"]]
        binds = dict(trigger=binding("PLAYER") if encoded else binding(),
                     cargo=binding("ACTOR", target["handle"]) if encoded else binding())
        rows.append(dict(handle=deepcopy(item["handle"]), role="WILD", available=True,
                         bindings=binds, rawBindingsHex=(raw_handle(item["handle"])
                             + bytes.fromhex(binds["trigger"]["rawHex"])
                             + bytes.fromhex(binds["cargo"]["rawHex"])).hex(),
                         throw=dict(targetRaw=encoded,
                                    targetSlot=(encoded & 63) - 1 if encoded else None,
                                    carried=bool(encoded & 128), windup=False,
                                    targeted=bool(target_mask & (1 << item["handle"]["slot"])),
                                    carrier=bool(carrier_mask & (1 << item["handle"]["slot"])),
                                    recovering=False)))
    combat = dict(schemaVersion=1, available=True, frame=frame, nativeCycle=s["nativeCycle"],
                  observationBoundary=s["observationBoundary"],
                  fieldSystem=s["fieldControl"]["fieldPointer"],
                  identity=dict(romSha256=ROM, overlaySha256=OVERLAY),
                  targets=[], movementTimers=[],
                  interactions=dict(schemaVersion=1, available=True, frame=frame,
                                    nativeCycle=s["nativeCycle"],
                                    observationBoundary=s["observationBoundary"],
                                    fieldSystem=s["fieldControl"]["fieldPointer"],
                                    identity=dict(romSha256=ROM), carriers=rows,
                                    throwState=state))
    for item in (a, b):
        combat["targets"].append(dict(handle=deepcopy(item["handle"]), role="WILD",
                                      motion=native_motion(item)))
        combat["movementTimers"].append(dict(handle=deepcopy(item["handle"]),
            slot=item["handle"]["slot"], sourceIdentity=deepcopy(item["sourceIdentity"]),
            movementActorControlMode=int(item is a and 4 <= frame <= 6)))
    s["pokemonCombat"] = combat
    return s


def events(s):
    if s["frame"] == 2:
        b, a = s["actors"][1], s["actors"][0]
        event = query_event(s, b, IMAGE, status=1)
        event["data"]["after"]["workspace"]["compatibility"]["cargo"] = deepcopy(a["handle"])
        raw = bytearray.fromhex(event["data"]["resultHex"])
        raw[:24] = raw_handle(b["handle"]) + raw_handle(a["handle"])
        event["data"]["resultHex"] = raw.hex()
        return [event]
    if s["frame"] == 7:
        a = s["actors"][0]
        return [dict(frame=7, kind="native", data=dict(event="MOTION_STARTED",
                    actorHandle=a["handle"]["value"],
                    actor={k: v for k, v in a["handle"].items() if k != "value"}))]
    return []


def meter():
    m = ThrowMutualPickupMeasurement(SOURCE)
    m.latest = sample(0)
    m.subjects = {name: select_current_actor(m.latest, item) for name, item in
                  (("geodude-a", m.latest["actors"][0]),
                   ("geodude-b", m.latest["actors"][1]))}
    return m


class MutualPickupTests(unittest.TestCase):
    def test_mutual_claims_one_held_owner_and_normal_launch(self):
        m = meter()
        for frame in range(1, 8):
            s = sample(frame)
            m._sample(s, events(s))
        self.assertTrue(m.result()["ready"])
        self.assertEqual(m.first_claim["frame"], 1)
        self.assertEqual(m.mutual["frame"], 2)
        self.assertEqual(m.pickup["frame"], 4)
        self.assertEqual(m.launch["frame"], 7)

    def test_copied_incoming_abort_and_physical_rejection(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                m = meter()
                negative = ThrowMutualPickupNegative(fault)
                negative.mutate(step_row(ACTIONS[0][0], [sample(0)]), m.subjects)
                failed = False
                for frame in range(1, 8):
                    s = sample(frame)
                    altered = negative.mutate(step_row(ACTIONS[0][0], [s]) | {"events": events(s)},
                                              m.subjects)
                    try:
                        m._sample(altered["samples"][0], altered["events"])
                    except (ValueError, KeyError, StopIteration):
                        failed = True
                        break
                self.assertTrue(negative.applied)
                self.assertTrue(failed)

    def test_exact_recipe_adapter_and_registration(self):
        path = ROOT / "tests/overworld/test-recipes" / f"{CASE}.json"
        value = json.loads(path.read_text())
        validate_recipe(value)
        from tools.overworld.proof_adapters import ADAPTERS
        from tools.overworld.devtools_test_contract import TestEvaluator
        self.assertEqual(ADAPTERS[KIND].recipe_subjects(), value["subjects"])
        evaluator = TestEvaluator(value)
        evaluator.install_measurements({KIND: SOURCE})
        self.assertIsInstance(evaluator.measurements[KIND], ThrowMutualPickupMeasurement)
        registry = json.loads((ROOT / "tools/overworld/runtime_proof_registry.json").read_text())
        self.assertEqual(registry["sharedTests"][CASE]["measurementContract"], contract())
        self.assertEqual(registry["sharedTests"][CASE]["recipeSha256"],
                         hashlib.sha256(path.read_bytes()).hexdigest())

    def test_independent_proof_rejects_wrong_full_owner(self):
        m = meter()
        for frame in range(1, 8):
            s = sample(frame)
            m._sample(s, events(s))
        result = dict(passed=True, failures=[], measurements={KIND: m.result()})
        record = dict(sessionId="fixture", sessionCleanup=dict(
            sessionId="fixture", closed=True, errors=[]))
        self.assertEqual(len(measurements(result, record)), 8)
        bad = deepcopy(result)
        bad["measurements"][KIND]["pickup"]["owner"]["handle"]["generation"] += 1
        with self.assertRaises(ValueError):
            measurements(bad, record)


if __name__ == "__main__":
    unittest.main()
