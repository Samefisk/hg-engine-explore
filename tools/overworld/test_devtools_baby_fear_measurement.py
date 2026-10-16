"""Focused completed-frame and copied-control checks for baby fear."""
from copy import deepcopy
import json
from pathlib import Path
import struct
import unittest

from tools.overworld.devtools_baby_fear_measurement import (
    BabyFearMeasurement, CASES, WILD_CRY, FOLLOWER_SAFETY, FOLLOWER_DAMAGED, WILD_DAMAGED, WILD_PLAYER, WILD_POKEMON,
    validate_recipe,
)
from tools.overworld.devtools_baby_fear_proof import (
    BabyFearNegative, contract, faults, measurements, validate_negative_result,
)
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_profile_feature_measurement import application_index
from tools.overworld.devtools_application_bank import canonical_bank, local_application
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_walk_matrix_observer import decode_motion, PHASES
from tools.overworld.test_devtools_player_health_throw_contact_measurement import actor

ROOT = Path(__file__).resolve().parents[2]
BANK = canonical_bank(ROOT)
SOURCE = dict(contractVersion=1, romSha256="a" * 64,
              overlaySha256="b" * 64, profileSha256="c" * 64)


def sample(kind, frame):
    case = CASES[kind]
    follower = case["role"] == "FOLLOWER"
    species = case.get("species", 173)
    y = 407 if follower else 402
    baby = actor(species, 0, species * 1000, y)
    baby["role"] = case["role"]
    baby.update(commitSequence=0, inputOwnership=0, reservationId=0,
                behaviorFingerprint=1717,
                matchedLayerMask=1 << local_application(
                    BANK, species, application_index(case["application"])))
    target_y = 408 if follower else 401 if case["target"] == "PLAYER" else 402
    target_x = 584 if kind == WILD_POKEMON else 585
    for field in ("logical", "origin", "target"):
        baby[field]["x"] = 585
    baby["target"].update(x=target_x, y=target_y)
    baby["engineObject"] = dict(pos_x=(585 << 16) + 32768,
                                pos_z=(y << 16) + 32768, pos_y=65536,
                                unk88_y=0, facing=1, flags=1)
    if frame >= 10:
        if frame <= 14:
            baby.update(motionKind="HOP" if kind == WILD_CRY else "WALK", motionPhase="MOVING" if frame < 14 else "COMMIT_PENDING",
                        motionElapsed=frame - 10, motionDuration=4)
            baby["engineObject"]["pos_x"] += (target_x - 585) * (frame - 10) * 16384
            baby["engineObject"]["pos_z"] += (target_y - y) * (frame - 10) * 16384
        else:
            baby.update(commitSequence=1, motionElapsed=4, motionDuration=4,
                        logical=dict(x=target_x, y=target_y))
            baby["engineObject"]["pos_x"] += (target_x - 585) * 65536
            baby["engineObject"]["pos_z"] += (target_y - y) * 65536
    actors = [baby]
    if any(s[0] == "threat" for s in case["subjects"]):
        threat_y = 406 if follower else 402
        threat_species = case["subjects"][1][1]
        threat = actor(threat_species, 2, threat_species * 1000, threat_y)
        for field in ("logical", "origin", "target"):
            threat[field]["x"] = 585 if follower else 586
        threat["role"] = "WILD"
        actors.append(threat)
    if not follower:
        passive = actor(155, 7, 155007, 407 if kind in (WILD_PLAYER, WILD_CRY) else 408)
        passive["role"] = "FOLLOWER"
        actors.append(passive)
    player_y = 410 if follower else 405 if kind in (WILD_PLAYER, WILD_CRY) else 408
    result = dict(frame=frame, nativeCycle=frame + 1000, fieldAvailable=True,
                romSha256=SOURCE["romSha256"], observationBoundary="main-task-queue-completion",
                context=dict(mapId=33, fieldEpoch=1, mapGeneration=1),
                fieldControl=dict(taskPointer=0, fieldPointer=0x2200000),
                actors=actors, player=dict(x=585, y=player_y),
                nativeObservation=dict(coverageComplete=True, profilesEvicted=0,
                                       profileFingerprints=[1717]))
    if case.get("damage"):
        hp = 100 if frame < 10 else 80
        result["party"] = [dict(personality=species * 1000, hp=hp, maxHp=100)] if follower else []
        raw = bytearray(52)
        struct.pack_into("<HBBHH4h2iHH", raw, 0, 1, 1, 1, 1, 1717,
                         585, y, target_x, target_y, 65536, 65536,
                         baby["motionDuration"], 9)
        raw[29], raw[35], raw[36] = 1, 1, 1
        struct.pack_into("<4H4B", raw, 40, baby["motionElapsed"], 0, 0,
                         baby["commitSequence"], PHASES.index(baby["motionPhase"]), 0, 0, 0)
        result["pokemonCombat"] = dict(schemaVersion=1, available=True, frame=frame,
            nativeCycle=frame+1000, identity=dict(overlaySha256=SOURCE["overlaySha256"],
            romSha256=SOURCE["romSha256"]), targets=[dict(handle=deepcopy(baby["handle"]),
            personality=species * 1000, species=species, role=case["role"], hp=hp,
            currentHp=hp, maxHp=100, hpSource="party" if follower else "wild-resident",
            hitCount=int(frame >= 10), lastDamage=20 if frame >= 10 else 0,
            immunityFrames=60-(frame-10) if frame >= 10 else 0,
            knockbackPending=0, motion=decode_motion(bytes(raw)))],
            movementTimers=[dict(handle=deepcopy(baby["handle"]), movementActorControlMode=0)])
    return result


def stream(kind):
    samples = [sample(kind, frame) for frame in range(10, 16)]
    baby = samples[0]["actors"][0]
    threat = samples[0]["actors"][1] if any(s[0] == "threat" for s in CASES[kind]["subjects"]) else None
    meter = BabyFearMeasurement(kind, SOURCE)
    data = bytearray(216)
    data[0], data[13] = CASES[kind]["behavior"]
    if CASES[kind]["role"] == "FOLLOWER" or kind in (WILD_CRY, WILD_DAMAGED):
        data[2], data[3] = 10, 10
    data[7] = 4 if CASES[kind]["role"] == "FOLLOWER" else 16
    data[12] = 2 if kind == WILD_CRY else 1
    struct.pack_into("<I", data, 192, 1717)
    player_target = CASES[kind]["target"] == "PLAYER"
    data[196:210] = (bytes(12) + bytes((1, 0)) if player_target
                     else raw_handle(threat["handle"]) + bytes((2, 0)))
    data[212] = meter.application_local
    struct.pack_into("<H", data, 214, meter.condition_id)
    events = []
    for frame, names in ((10, ("CONDITIONAL_RESOLVED", "INTENT_CREATED", "MOTION_STARTED")),
                         (15, ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED"))):
        for seq, name in enumerate(names):
            value = dict(actorHandle=baby["handle"]["value"],
                         actor={k: v for k, v in baby["handle"].items() if k != "value"},
                         sequence=frame * 10 + seq, event=name, actorFrame=frame,
                         valueA=0, valueB=0, reasonId=0)
            if name == "CONDITIONAL_RESOLVED":
                value.update(reasonId=meter.application_local | (meter.application_local << 5)
                             | ((1 if player_target else 2) << 10) | (1 << 12)
                             | (1 << 13) | (1 << 14) | (1 << 15),
                             valueA=meter.condition_id
                             | ((0 if player_target else threat["handle"]["slot"]) << 16))
                if CASES[kind].get("damage") or kind == WILD_CRY:
                    value["valueB"] = ((frame + 960) & 0xFFFF) | (((frame + 970) & 0xFFFF) << 16)
            elif name == "MOTION_STARTED":
                value.update(valueA=2 if kind == WILD_CRY else 1, valueB=4)
            events.append(dict(frame=frame, kind="native", data=value))
    if kind == FOLLOWER_SAFETY or kind == WILD_CRY:
        subject = dict(handle=deepcopy(baby["handle"]), species=CASES[kind].get("species", 173), form=0,
                       role=CASES[kind]["role"])
        if kind == WILD_CRY:
            subject.update({k: baby[k] for k in ("subjectIdentity", "authorityGeneration",
                           "engineAnchorGeneration", "presentationGeneration")})
        pointer = baby["engineIdentity"]["pointer"] if kind == WILD_CRY else 0x02210000
        events.insert(1, dict(frame=10, kind="native-observation", data=dict(
            observation="safety-bubble", publicSubject=subject,
            publicSubjectAfter=deepcopy(subject), bubbleId=10, returnValue=0x02337860,
            objectPointer=pointer, sourceObjectPointer=pointer,
            engineObjectPointer=pointer)))
    row = dict(phase="observe", action=CASES[kind]["actions"][-1][0],
               samples=samples, events=events, completedGameFrames=6,
               observedFieldFrames=6, nativeCycles=6,
               cycleIntervals=[dict(completedGameFrame=s["frame"], cpuNs=1, wallNs=1)
                               for s in samples],
               profileCache=dict(frame=15, nativeCycle=1015,
                                 resolvedProfiles=[dict(fingerprint=1717, resolved=True,
                                                        sourceSha256=SOURCE["profileSha256"],
                                                        resultHex=data.hex())]))
    return [row]


def evaluate(kind, rows, negative=None):
    meter = BabyFearMeasurement(kind, SOURCE)
    initial = sample(kind, 9)
    meter.latest = deepcopy(initial)
    meter.setup_index = len(CASES[kind]["setup"])
    meter.subjects = {name: select_current_actor(initial, actor_row)
                      for name, actor_row in zip((s[0] for s in CASES[kind]["subjects"]),
                                                 initial["actors"])}
    if CASES[kind].get("damage"):
        meter.previous_hp_row = deepcopy(meter._hp_row(initial))
        meter.previous_hp = meter._hp(initial)
    for row in rows:
        meter.observe_record(negative.mutate(row, meter.subjects) if negative else row)
    result = meter.finish()
    return dict(passed=result["passed"], failures=result["failures"],
                observedFrames=result["observedFrames"], measurements={kind: result})


class BabyFearTests(unittest.TestCase):
    def test_all_three_exact_sources_and_completed_motions(self):
        for kind in CASES:
            with self.subTest(kind=kind):
                replay = evaluate(kind, stream(kind))
                self.assertTrue(replay["passed"], replay)
                proof = measurements(kind, replay, dict(sessionId="owned",
                    sessionCleanup=dict(sessionId="owned", closed=True, errors=[])))
                self.assertEqual(len(proof), len(contract(kind)))

    def test_copied_fear_faults_reject_for_the_named_reason(self):
        for kind in CASES:
            for fault in faults(kind):
                with self.subTest(kind=kind, fault=fault):
                    negative = BabyFearNegative(kind, fault)
                    result = evaluate(kind, stream(kind), negative)
                    self.assertTrue(negative.applied, fault)
                    validate_negative_result(kind, result, fault)

    def test_follower_target_and_role_cannot_be_substituted(self):
        kind = FOLLOWER_SAFETY
        for field in ("player", "role", "condition"):
            rows = stream(kind)
            if field == "player":
                for s in rows[0]["samples"]: s["player"]["y"] = 406
            elif field == "role":
                for s in rows[0]["samples"]: s["actors"][0]["role"] = "WILD"
            else:
                rows[0]["events"][0]["data"]["valueA"] ^= 1
            self.assertFalse(evaluate(kind, rows)["passed"], field)

    def test_timed_fear_can_hold_after_truth_clears(self):
        for kind in CASES:
            rows = stream(kind)
            held = deepcopy(rows[0]["events"][0])
            held["frame"] = 11
            held["data"]["actorFrame"] = 11
            held["data"]["sequence"] = 110
            held["data"]["reasonId"] &= ~((1 << 12) | (1 << 13))
            rows[0]["events"].insert(3, held)
            self.assertTrue(evaluate(kind, rows)["passed"], kind)
            rows[0]["events"] = [e for e in rows[0]["events"]
                                 if not (e["frame"] == 10 and e["data"].get("event") == "CONDITIONAL_RESOLVED")]
            self.assertFalse(evaluate(kind, rows)["passed"], kind)

    def test_damage_knockback_is_skipped_before_the_first_free_response(self):
        for kind in (FOLLOWER_DAMAGED, WILD_DAMAGED):
            row = stream(kind)[0]
            condition = deepcopy(row["events"][0])
            forced = []
            for frame in range(10, 23):
                current = sample(kind, 10)
                current.update(frame=frame, nativeCycle=frame + 1000)
                subject = current["actors"][0]
                subject.update(motionKind="HOP", motionPhase="MOVING",
                               motionElapsed=frame - 10, motionDuration=13)
                combat = current["pokemonCombat"]
                combat.update(frame=frame, nativeCycle=frame + 1000)
                hp = combat["targets"][0]
                raw = bytearray.fromhex(hp["motion"]["rawHex"])
                raw[2], raw[30], raw[37] = 2, 16, 1
                struct.pack_into("<H", raw, 24, 13)
                struct.pack_into("<H", raw, 40, frame - 10)
                hp["motion"] = decode_motion(bytes(raw))
                hp["immunityFrames"] = 60 - (frame - 10)
                subject["engineObject"]["pos_z"] += (subject["target"]["y"] - subject["origin"]["y"]) \
                    * (frame - 10) * 65536 // 13
                forced.append(current)
            for current in row["samples"]:
                current["frame"] += 13
                current["nativeCycle"] += 13
                current["pokemonCombat"]["frame"] += 13
                current["pokemonCombat"]["nativeCycle"] += 13
                current["pokemonCombat"]["targets"][0]["immunityFrames"] -= 13
                subject = current["actors"][0]
                shift = subject["target"]["y"] - subject["origin"]["y"]
                for position in ("logical", "origin", "target", "render"):
                    subject[position]["y"] += shift
                subject["engineObject"]["pos_z"] += shift * 65536
                subject["commitSequence"] += 1
                hp = current["pokemonCombat"]["targets"][0]
                raw = bytearray.fromhex(hp["motion"]["rawHex"])
                struct.pack_into("<h", raw, 10, subject["origin"]["y"])
                struct.pack_into("<h", raw, 14, subject["target"]["y"])
                struct.pack_into("<H", raw, 46, subject["commitSequence"])
                hp["motion"] = decode_motion(bytes(raw))
            for event in row["events"][1:]:
                event["frame"] += 13
                event["data"]["actorFrame"] += 13
                event["data"]["sequence"] += 130
            row["events"] = [condition] + row["events"][1:]
            row["samples"] = forced + row["samples"]
            row.update(completedGameFrames=19, observedFieldFrames=19, nativeCycles=19,
                       cycleIntervals=[dict(completedGameFrame=s["frame"], cpuNs=1, wallNs=1)
                                       for s in row["samples"]])
            row["profileCache"].update(frame=28, nativeCycle=1028)
            result = evaluate(kind, [row])
            self.assertTrue(result["passed"], result)
            self.assertEqual(result["measurements"][kind]["witness"]["startFrame"], 23)
            self.assertEqual(result["measurements"][kind]["subjectDamage"]["frame"], 10)

    def test_wild_damage_requires_authored_cry_and_alert_time(self):
        kind = WILD_DAMAGED
        self.assertTrue(evaluate(kind, stream(kind))["passed"])
        for alert in ((0, 0), (0, 10), (10, 0), (7, 10), (10, 9), (3, 10)):
            rows = stream(kind)
            profile = rows[0]["profileCache"]["resolvedProfiles"][0]
            raw = bytearray.fromhex(profile["resultHex"])
            raw[2:4] = bytes(alert)
            profile["resultHex"] = raw.hex()
            result = evaluate(kind, rows)
            with self.subTest(alert=alert):
                self.assertFalse(result["passed"])
                self.assertIn("Wild self damage response lacks authored Anguish10 and alert time10",
                              " ".join(result["failures"]))

    def test_wild_damage_cry_cannot_replace_full_winner_target_or_role(self):
        kind = WILD_DAMAGED
        for offset in (192, 196, 208, 212, 213, 214):
            rows = stream(kind)
            profile = rows[0]["profileCache"]["resolvedProfiles"][0]
            raw = bytearray.fromhex(profile["resultHex"])
            raw[offset] ^= 1
            profile["resultHex"] = raw.hex()
            with self.subTest(offset=offset):
                self.assertFalse(evaluate(kind, rows)["passed"])
        for role in ("FOLLOWER", "MOUNTED"):
            rows = stream(kind)
            for current in rows[0]["samples"]:
                current["actors"][0]["role"] = role
                current["pokemonCombat"]["targets"][0]["role"] = role
            with self.subTest(role=role):
                self.assertFalse(evaluate(kind, rows)["passed"])

    def test_damage_identity_native_plan_and_timing_cannot_be_substituted(self):
        for kind in (FOLLOWER_DAMAGED, WILD_DAMAGED):
            for fault in ("foreign-hp", "wrong-hp-owner", "input-control", "old-intent",
                          "motion-raw-parity", "wrong-cooldown"):
                with self.subTest(kind=kind, fault=fault):
                    row = stream(kind)[0]
                    if fault == "old-intent":
                        for event in row["events"]:
                            if event["data"]["event"] == "INTENT_CREATED":
                                event["data"]["sequence"] = 99
                    elif fault == "wrong-cooldown":
                        row["events"][0]["data"]["valueB"] ^= 1 << 16
                    else:
                        for current in row["samples"]:
                            hp = current["pokemonCombat"]["targets"][0]
                            if fault == "foreign-hp":
                                hp["personality"] ^= 1
                            elif fault == "wrong-hp-owner":
                                hp["hpSource"] = "wild-resident" if kind == FOLLOWER_DAMAGED else "party"
                            elif fault == "input-control":
                                current["actors"][0]["inputOwnership"] = 1
                            else:
                                hp["motion"]["plan"]["flags"] = 1
                    self.assertFalse(evaluate(kind, [row])["passed"])

    def test_damage_timing_wraps_at_the_native_trace_halfword(self):
        for kind in (FOLLOWER_DAMAGED, WILD_DAMAGED):
            row = stream(kind)[0]
            event = row["events"][0]["data"]
            event["actorFrame"] = 65530
            event["valueB"] = ((65530 + 960) & 0xFFFF) | (((65530 + 970) & 0xFFFF) << 16)
            self.assertTrue(evaluate(kind, [row])["passed"])

    def test_old_follow_move_does_not_count_as_fast_safety_response(self):
        rows = stream(FOLLOWER_SAFETY)
        for sample_row in rows[0]["samples"]:
            sample_row["actors"][0]["motionDuration"] = 8
        result = evaluate(FOLLOWER_SAFETY, rows)
        self.assertFalse(result["passed"])
        self.assertIsNone(result["measurements"][FOLLOWER_SAFETY]["witness"])

    def test_saved_mankey_cannot_replace_exact_passive_follower(self):
        for kind in (WILD_PLAYER, WILD_POKEMON):
            rows = stream(kind)
            for sample_row in rows[0]["samples"]:
                sample_row["actors"][-1]["species"] = 56
            self.assertFalse(evaluate(kind, rows)["passed"], kind)

    def test_setup_condition_event_is_the_copied_fault_owner(self):
        for kind in (WILD_POKEMON, FOLLOWER_SAFETY):
            meter = BabyFearMeasurement(kind, SOURCE)
            current = sample(kind, 10)
            meter.subjects = {name: select_current_actor(current, row)
                              for name, row in zip((s[0] for s in CASES[kind]["subjects"]),
                                                   current["actors"])}
            event = deepcopy(stream(kind)[0]["events"][0])
            row = dict(phase="setup", action="bind-threat", receipt=dict(events=[event]))
            negative = BabyFearNegative(kind, kind + ":wrong-condition")
            changed = negative.mutate(row, meter.subjects)
            self.assertTrue(negative.applied)
            self.assertNotEqual(changed["receipt"]["events"][0]["data"]["valueA"],
                                row["receipt"]["events"][0]["data"]["valueA"])
            meter._events(current, changed["receipt"]["events"])
            self.assertIsNone(meter.condition)

    def test_igglybuff_approach_matches_measured_four_input_five_queue_baseline(self):
        path = ROOT / "tests/overworld/test-recipes/wild.igglybuff-player-fear-cry.json"
        recipe = json.loads(path.read_text())
        validate_recipe(recipe)
        self.assertEqual(recipe["actions"][0]["args"], {"frames": 5, "keys": ["RIGHT"]})
        self.assertEqual(recipe["actions"][1]["args"], {"frames": 32, "keys": ["UP"]})
        self.assertEqual(recipe["actions"][2]["args"]["frames"], 180)
        self.assertEqual(recipe["budgets"]["maxFrames"], 600)
        self.assertEqual(CASES[WILD_PLAYER]["actions"][0][2]["frames"], 4)
        for index, key, value in ((0, "frames", 4), (0, "frames", 6),
                                  (0, "keys", ["LEFT"]), (1, "frames", 31),
                                  (2, "frames", 181)):
            changed = deepcopy(recipe)
            changed["actions"][index]["args"][key] = value
            with self.subTest(index=index, key=key, value=value), self.assertRaisesRegex(
                    ValueError, "recipe differs from the bounded normal trigger"):
                validate_recipe(changed)

    def test_wild_igglybuff_requires_real_cry_full_body_and_stock_admission(self):
        good = stream(WILD_CRY)
        self.assertTrue(evaluate(WILD_CRY, good)["passed"])
        for field, value in (("bubbleId", 7), ("returnValue", 0),
                             ("objectPointer", 0x02210000)):
            rows = deepcopy(good)
            bubble = next(e["data"] for e in rows[0]["events"]
                          if e["kind"] == "native-observation")
            bubble[field] = value
            self.assertFalse(evaluate(WILD_CRY, rows)["passed"], field)
        for field in ("subjectIdentity", "authorityGeneration", "presentationGeneration"):
            rows = deepcopy(good)
            bubble = next(e["data"] for e in rows[0]["events"]
                          if e["kind"] == "native-observation")
            bubble["publicSubject"][field] += 1
            bubble["publicSubjectAfter"] = deepcopy(bubble["publicSubject"])
            self.assertFalse(evaluate(WILD_CRY, rows)["passed"], field)
        rows = deepcopy(good)
        for actor_sample in rows[0]["samples"]:
            actor_sample["actors"][0]["motionKind"] = "WALK"
        self.assertFalse(evaluate(WILD_CRY, rows)["passed"])

    def test_wild_igglybuff_requires_original_notice_duration_and_resolved_cry(self):
        for offset in (2, 3, 12):
            rows = stream(WILD_CRY)
            raw = bytearray.fromhex(rows[0]["profileCache"]["resolvedProfiles"][0]["resultHex"])
            raw[offset] ^= 1
            rows[0]["profileCache"]["resolvedProfiles"][0]["resultHex"] = raw.hex()
            self.assertFalse(evaluate(WILD_CRY, rows)["passed"], offset)
        rows = stream(WILD_CRY)
        rows[0]["events"][0]["data"]["valueB"] ^= 1
        self.assertFalse(evaluate(WILD_CRY, rows)["passed"])

    def test_igglybuff_setup_keeps_exact_native_offscreen_hop(self):
        from tools.overworld.devtools_test_contract import _wild_spawn_setup
        from tools.overworld.test_devtools_wild_walk_contract import spawn_setup

        def fixture(origin=(0, -8), direction=1):
            receipt, current = spawn_setup(species=174, locomotion=4)
            native = receipt["events"][0]["data"]
            prefix = bytearray.fromhex(native["preparedPrefixHex"])
            struct.pack_into("<2h", prefix, 24, *origin)
            prefix[29] = direction
            native["preparedPrefixHex"] = prefix.hex()
            native["startup"].update(origin=list(origin), hopDirection=direction)
            final = native["finalization"]["receipt"]
            final.update(preparedPrefixHex=prefix.hex(), startup=deepcopy(native["startup"]))
            body = current["actors"][0]
            body["logical"] = dict(x=origin[0], y=origin[1])
            native["publicSubject"] = deepcopy(body)
            return receipt, current

        receipt, current = fixture()
        bound = _wild_spawn_setup(receipt, current, species=174, locomotion=4)
        self.assertEqual(bound["destination"], [0, 0])
        self.assertEqual(bound["nativeSpawn"]["data"]["startup"]["origin"], [0, -8])
        for origin, direction in (((0, -7), 1), ((0, -9), 1), ((1, -8), 1),
                                  ((0, 0), 1), ((0, -8), 0)):
            receipt, current = fixture(origin, direction)
            with self.subTest(origin=origin, direction=direction), self.assertRaises(ValueError):
                _wild_spawn_setup(receipt, current, species=174, locomotion=4)
        for fault in ("owner", "field", "body-site", "unmatched-finalizer"):
            receipt, current = fixture()
            if fault == "owner":
                receipt["value"]["personality"] += 1
            elif fault == "field":
                current["context"]["fieldEpoch"] += 1
            elif fault == "body-site":
                current["actors"][0]["logical"]["y"] += 1
            else:
                receipt["events"][0]["data"]["finalization"]["status"] = "unmatched"
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                _wild_spawn_setup(receipt, current, species=174, locomotion=4)

    def test_registered_recipes_and_adapters(self):
        from tools.overworld.control import _shared_test_registration
        from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
        from tools.overworld.devtools_test_inputs import measurement_inputs
        from tools.overworld.proof_adapters import get_adapter
        for kind, case in CASES.items():
            with self.subTest(kind=kind):
                path = ROOT / "tests/overworld/test-recipes" / (case["test"] + ".json")
                recipe = validate_test(json.loads(path.read_text()))
                validate_recipe(recipe)
                registration, _ = _shared_test_registration(recipe, ROOT)
                source = measurement_inputs(recipe, ROOT)
                self.assertEqual(set(source[kind]),
                                 {"contractVersion", "romSha256", "overlaySha256", "profileSha256"})
                evaluator = TestEvaluator(recipe)
                evaluator.install_measurements(source)
                self.assertIsInstance(evaluator.measurements[kind], BabyFearMeasurement)
                adapter = get_adapter(kind)
                self.assertEqual(adapter.contract(), registration["measurementContract"])
                self.assertEqual(adapter.recipe_subjects(), recipe["subjects"])

    def test_damage_setup_authenticates_ambush_threat_in_place(self):
        from unittest.mock import patch
        from tools.overworld.devtools_test_contract import TestEvaluator
        from tools.overworld.test_devtools_wild_walk_contract import spawn_setup

        for kind in (FOLLOWER_DAMAGED, WILD_DAMAGED):
            for locomotion in (0, 7):
                with self.subTest(kind=kind, locomotion=locomotion):
                    recipe = json.loads((ROOT / "tests/overworld/test-recipes"
                        / (CASES[kind]["test"] + ".json")).read_text())
                    evaluator = TestEvaluator(recipe)
                    evaluator.install_measurements({kind: SOURCE})
                    receipt, current = spawn_setup(species=70, locomotion=locomotion)
                    row = dict(phase="setup", action="spawn-threat", command="spawn",
                               receipt=receipt, snapshot=current)
                    # Isolate the setup gate; this supplies no damage/fear proof.
                    with patch.object(evaluator.measurements[kind], "observe_record",
                            return_value=dict(failures=[], observedFrames=0)) as measured:
                        result = evaluator.observe_record(row)
                    if locomotion == 0:
                        self.assertFalse(result["failures"], result["failures"])
                        measured.assert_called_once()
                    else:
                        self.assertIn("wild Walk spawn identity or own native destination differs",
                                      str(result["failures"]))
                        measured.assert_not_called()


if __name__ == "__main__":
    unittest.main()
