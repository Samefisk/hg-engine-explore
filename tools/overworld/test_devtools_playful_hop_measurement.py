"""Focused actual observation shape and copied fault controls for Playful hops."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.overworld.devtools_playful_hop_measurement import (
    APPLICATION, FIND_APPLICATION, FIND_PLAYER_CONDITION, PLAYER_CONDITION, KIND,
    PlayfulHopMeasurement, validate_recipe,
)
from tools.overworld.devtools_application_bank import canonical_bank, local_application
from tools.overworld.devtools_playful_hop_proof import PlayfulHopNegative, contract
from tools.overworld.devtools_test_contract import TestEvaluator, validate_test
from tools.overworld.devtools_test_inputs import measurement_inputs
from tools.overworld.control import _shared_test_registration
from tools.overworld.proof_adapters import get_adapter
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.test_devtools_player_health_throw_contact_measurement import actor

ROOT = Path(__file__).resolve().parents[2]
APPLICATION_LOCAL = local_application(canonical_bank(ROOT), 35, APPLICATION)
FIND_APPLICATION_LOCAL = local_application(canonical_bank(ROOT), 35, FIND_APPLICATION)
SOURCE = dict(contractVersion=1, romSha256="a" * 64, overlaySha256="b" * 64,
              profileSha256="c" * 64)


def frame(number, command=255, spot=0, height=0, *, x=585):
    clefairy = actor(35, 0, 35000, 404)
    clefairy["logical"]["x"] = x
    clefairy.update(behaviorFingerprint=1234, matchedLayerMask=(1 << APPLICATION_LOCAL) | (1 << FIND_APPLICATION_LOCAL))
    clefairy["engineObject"].update(pos_y=65536, face_y=height, unk88_y=0,
                                    flags=2 if spot else 0, movement_cmd=command,
                                    pos_x=(585 << 16) + 0x8000)
    passive = actor(155, 7, 155000, 407)
    passive["role"] = "FOLLOWER"
    return dict(frame=number, nativeCycle=number + 1000, fieldAvailable=True,
                observationBoundary="main-task-queue-completion", romSha256=SOURCE["romSha256"],
                context=dict(mapId=33, fieldEpoch=1, mapGeneration=1), player=dict(x=585, y=405),
                fieldControl=dict(taskPointer=0), actors=[clefairy, passive],
                pokemonCombat=dict(movementTimers=[dict(handle=clefairy["handle"],
                    sourceIdentity=None, movementActorControlMode=0,
                    movementSpotState=spot, movementEmoteTimer=8 if spot else 0)]))


def meter():
    instance = PlayfulHopMeasurement(SOURCE)
    first = frame(1)
    instance.subjects = {name: select_current_actor(first, row) for name, row in
                         (("clefairy", first["actors"][0]), ("passive", first["actors"][1]))}
    instance.active_condition = dict(conditionId=PLAYER_CONDITION, targetKind=1, targetSlot=0)
    instance.find_condition = dict(conditionId=FIND_PLAYER_CONDITION, active=True, targetKind=1, targetSlot=0, activeUntil=785, cooldownUntil=795)
    instance.approach = dict(actor=instance.subjects["clefairy"]["handle"], condition=dict(conditionId=FIND_PLAYER_CONDITION))
    return instance


def selected(count, number, *, heart=False, cry=False):
    return dict(count=count, selectedFrame=number, condition=dict(conditionId=PLAYER_CONDITION),
                fingerprint=1234, tile=None, baseY=None, commit=None, commands=[], arcMax=[],
                started=False, releasedFrame=None, lastCommand=None, jumpFrames=[], policy={},
                sequence=dict(returnValue=1), decisions=dict(heart=heart, cry=cry), stepEvents={}, prepEvents={}, heartDraws=[])


def condition_event(sample, *, truth, triggered, sequence, until=0, find=False):
    handle = sample["actors"][0]["handle"]
    application = FIND_APPLICATION_LOCAL if find else APPLICATION_LOCAL
    reason = (application | (application << 5) | (1 << 10) | (1 << 14) | ((1 << 15) if find else 0)
              | ((1 << 12) if triggered else 0) | ((1 << 13) if truth else 0))
    return dict(frame=sample["frame"], kind="native", data=dict(event="CONDITIONAL_RESOLVED",
        actorHandle=handle["value"], actor={k: v for k, v in handle.items() if k != "value"},
        actorFrame=sample["frame"] - 468, sequence=sequence, reasonId=reason,
        valueA=FIND_PLAYER_CONDITION if find else PLAYER_CONDITION, valueB=until | ((795 << 16) if find else 0)))


def drive(instance, count, start, *, heart=False, cry=False, missing=False,
          displaced=False, raised_valley=False, missing_heart=False,
          unexpected_heart=False, wrong_cry=False, instant_prep=False, missing_prep=False,
          continued_heart=False, hidden_heart=False, handoff_delay=0, expired_jump=False,
          existing_heart=False):
    instance.pending = selected(count, start - 1, heart=heart, cry=cry)
    commands = [item for _ in range(count) for item in (0x49, 0x30, 0x3E, 0x4A)]
    if instant_prep:
        commands = [command for command in commands if command != 0x49]
    for offset, command in enumerate(commands):
        if missing and offset == 5:
            command = 0x34
        height = 0x3000 if command == 0x30 or raised_valley and offset == 2 else 0
        sample = frame(start + offset, command, 1, height,
                       x=586 if displaced and offset == 1 else 585)
        if expired_jump and command == 0x30:
            sample["pokemonCombat"]["movementTimers"][0]["movementEmoteTimer"] = 0
        events = []
        if not missing_prep and (command == 0x49 or instant_prep and command == 0x30):
            owner = select_current_actor(sample, sample["actors"][0])
            events.append(dict(kind="native-observation", frame=sample["frame"], data=dict(
                observation="playful-step", stepId=(start + offset) * 2,
                publicSubject=owner, publicSubjectAfter=owner, returnValue=1, command=0x49,
                heartCalls=0, cryCalls=0, objectPose=dict(pos_x=(585 << 16) + 0x8000,
                    pos_z=(404 << 16) + 0x8000, pos_y=65536, face_y=0, unk88_y=0))))
        if 0x30 <= command <= 0x33:
            owner = select_current_actor(sample, sample["actors"][0])
            step_id = start + offset
            base = dict(kind="native-observation", frame=sample["frame"])
            if heart and not missing_heart or unexpected_heart:
                events.append(dict(base, data=dict(observation="playful-heart", stepId=step_id,
                    publicSubject=owner, bubbleId=0,
                    returnValue=0 if existing_heart or continued_heart and offset >= 4 else 0x02337860)))
            if cry:
                events.append(dict(base, data=dict(observation="playful-cry", stepId=step_id,
                    publicSubject=owner, species=36 if wrong_cry else 35, form=0)))
            events.append(dict(base, data=dict(observation="playful-step", stepId=step_id,
                publicSubject=owner, publicSubjectAfter=owner, returnValue=1, command=command)))
            if heart:
                events.append(dict(base, data=dict(observation="playful-heart-draw",
                    publicSubject=owner, bubbleId=0, effectPointer=0x02337860,
                    modelPointer=0x02340000, visible=not hidden_heart, hidden=1 if hidden_heart else 0)))
        instance._sample(sample, events, None)
    for offset in range(handoff_delay):
        sample = frame(start + len(commands) + offset, 255, 1)
        sample["pokemonCombat"]["movementTimers"][0]["movementEmoteTimer"] = 0
        sample["actors"][0]["engineObject"]["flags"] = 0
        instance._sample(sample, [], None)
    instance._sample(frame(start + len(commands) + handoff_delay, 255, 0), [], None)


class PlayfulHopTests(unittest.TestCase):
    def test_recipe_and_contract(self):
        recipe = json.loads((ROOT / "tests/overworld/test-recipes/profile.playful.in-place-hop.json").read_text())
        validate_recipe(recipe)
        self.assertEqual(set(contract()), {"live-actor-identity", "profile-resolution",
                                           "rendered-motion", "control-release", "feedback-effect"})
        wrong = deepcopy(recipe)
        wrong["actions"][0]["args"]["keys"] = ["B"]
        with self.assertRaisesRegex(ValueError, "typed recipe"):
            validate_recipe(wrong)

    def test_live_and_replay_use_exact_four_field_source(self):
        recipe = validate_test(json.loads((ROOT / "tests/overworld/test-recipes/profile.playful.in-place-hop.json").read_text()))
        registration, _ = _shared_test_registration(recipe, ROOT)
        live_source = measurement_inputs(recipe, ROOT)
        replay_source = measurement_inputs(recipe, ROOT)
        self.assertEqual(live_source, replay_source)
        source = live_source[KIND]
        self.assertEqual(set(source), {"contractVersion", "romSha256", "overlaySha256", "profileSha256"})
        self.assertEqual(source["contractVersion"], 1)
        self.assertEqual(source["romSha256"], hashlib.sha256((ROOT / "test.nds").read_bytes()).hexdigest())
        self.assertEqual(source["profileSha256"], hashlib.sha256(
            (ROOT / "data/overworld_behavior_profiles.json").read_bytes()).hexdigest())
        descriptor = json.loads((ROOT / "build/player-health.debug.json").read_text())
        self.assertEqual(source["overlaySha256"], descriptor["overlay"]["sha256"])
        evaluator = TestEvaluator(recipe)
        evaluator.install_measurements(live_source)
        self.assertIsInstance(evaluator.measurements[KIND], PlayfulHopMeasurement)
        self.assertEqual(get_adapter(KIND).contract(), registration["measurementContract"])
        self.assertEqual(get_adapter(KIND).recipe_subjects(), recipe["subjects"])

    def test_both_complete_counts_same_actor(self):
        instance = meter()
        drive(instance, 1, 10, heart=True, cry=True)
        drive(instance, 1, 20)
        drive(instance, 2, 30, heart=True, cry=True)
        drive(instance, 2, 50)
        instance.admission_skip = dict(actor=instance.subjects["clefairy"]["handle"])
        self.assertTrue(instance.result()["ready"])
        self.assertEqual([len(instance.outcomes[n]["arcMax"]) for n in (1, 2)], [1, 2])
        self.assertEqual(instance.outcomes[1]["commands"], [0x49, 0x30, 0x3E, 0x4A])

    def test_missing_second_hop_rejects(self):
        instance = meter()
        with self.assertRaisesRegex(ValueError, "stock one/two-hop"):
            drive(instance, 2, 20, missing=True)

    def test_prep_and_jump_in_one_completed_frame_keep_exact_native_phase(self):
        instance = meter()
        drive(instance, 2, 10, instant_prep=True)
        self.assertEqual(instance.outcomes[2]["commands"], [0x49, 0x30, 0x3E, 0x4A] * 2)
        self.assertEqual(len(instance.outcomes[2]["prepEvents"]), 2)

    def test_sampled_prep_without_native_acceptance_cannot_pass(self):
        with self.assertRaisesRegex(ValueError, "accepted native PREP boundary"):
            drive(meter(), 1, 10, missing_prep=True)

    def test_exact_stock_bob_only_at_accepted_jump_start(self):
        def begin(*, stage=0, bob=1, height=-8192, event_frame=10):
            instance = meter()
            instance.pending = selected(1, 9)
            sample = frame(10, 0x30, 1, height)
            sample["actors"][0]["engineObject"].update(
                movement_step=stage, movement_render_words=[0] * 5 + [bob << 8])
            owner = select_current_actor(sample, sample["actors"][0])
            base = dict(kind="native-observation", frame=10)
            events = [dict(base, data=dict(observation="playful-step", stepId=20,
                publicSubject=owner, publicSubjectAfter=owner, returnValue=1, command=0x49,
                heartCalls=0, cryCalls=0, objectPose=dict(pos_x=(585 << 16) + 0x8000,
                    pos_z=(404 << 16) + 0x8000, pos_y=65536, face_y=0, unk88_y=0))),
                dict(base, data=dict(observation="playful-step", stepId=21,
                    publicSubject=owner, publicSubjectAfter=owner, returnValue=1, command=0x30))]
            if event_frame != 10:
                # A retained prior receipt cannot license a later negative arc.
                instance.pending["baseY"] = 65536
                instance.pending["stepEvents"][21] = dict(
                    frame=event_frame, command=0x30, heart=[], cry=[])
                events = []
            instance._sample(sample, events, None)
            return instance

        instance = begin()
        instance._sample(frame(11, 0x30, 1, 0x3000), [], None)
        instance._sample(frame(12, 0x3E, 1), [], None)
        instance._sample(frame(13, 0x4A, 1), [], None)
        instance._sample(frame(14), [], None)
        self.assertEqual(instance.outcomes[1]["stockStartBobs"], [10])
        self.assertEqual(instance.outcomes[1]["arcMax"], [0x3000])
        for changes in ({"stage": 1}, {"bob": 0}, {"height": -4096}, {"event_frame": 9}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "stock Hop arc"):
                begin(**changes)

    def test_missing_prep_control_removes_only_actual_accepted_native_call(self):
        instance = meter()
        owner = instance.subjects["clefairy"]["handle"]
        event = dict(kind="native-observation", frame=10, data=dict(
            observation="playful-step", command=0x49, returnValue=1,
            publicSubject=dict(handle=owner)))
        row = dict(phase="observe", events=[event], samples=[frame(10, 0x30, 1, 4096)])
        fault = PlayfulHopNegative("missing-prep")
        copied = fault.mutate(row, instance.subjects)
        self.assertTrue(fault.applied)
        self.assertEqual(copied["events"], [])
        self.assertEqual(copied["samples"], row["samples"])
        self.assertEqual(row["events"], [event])

    def test_missing_second_hop_control_uses_native_prep_when_not_sampled(self):
        instance = meter()
        owner = dict(handle=instance.subjects["clefairy"]["handle"])
        response = bytearray(28); response[22:24] = bytes((1, 2))
        policy = dict(kind="native-observation", frame=9, data=dict(
            observation="walk-policy", operation=4, publicSubject=owner,
            responseHex=response.hex()))
        steps = [dict(kind="native-observation", frame=number, data=dict(
            observation="playful-step", publicSubject=owner, returnValue=1, command=command))
            for number, command in ((10, 0x49), (10, 0x30), (13, 0x49), (13, 0x30))]
        row = dict(phase="observe", events=[policy] + steps,
                   samples=[frame(10, 0x30, 1, 4096), frame(13, 0x30, 1, 4096)])
        fault = PlayfulHopNegative("missing-second-hop")
        copied = fault.mutate(row, instance.subjects)
        self.assertTrue(fault.applied)
        self.assertEqual([s["actors"][0]["engineObject"]["movement_cmd"]
                          for s in copied["samples"]], [0x30, 0x34])

    def test_displacement_rejects(self):
        instance = meter()
        with self.assertRaisesRegex(ValueError, "in-place Hop changed"):
            drive(instance, 1, 10, displaced=True)

    def test_displacement_control_waits_for_the_selected_jump(self):
        instance = meter()
        fault = PlayfulHopNegative("displacement")
        unrelated = dict(phase="observe", events=[], samples=[frame(8, 0x49, 1)])
        self.assertEqual(fault.mutate(unrelated, instance.subjects), unrelated)
        self.assertFalse(fault.applied)
        owner = dict(handle=instance.subjects["clefairy"]["handle"])
        response = bytearray(28); response[22:24] = bytes((1, 1))
        policy = dict(kind="native-observation", frame=9, data=dict(
            observation="walk-policy", operation=4, publicSubject=owner,
            responseHex=response.hex()))
        jump = dict(kind="native-observation", frame=10, data=dict(
            observation="playful-step", publicSubject=owner, returnValue=1, command=0x30))
        row = dict(phase="observe", events=[policy, jump],
                   samples=[frame(10, 0x30, 1), frame(11, 0x30, 1, 4096)])
        copied = fault.mutate(row, instance.subjects)
        self.assertTrue(fault.applied)
        self.assertEqual(copied["events"], row["events"])
        self.assertEqual(copied["samples"][0], row["samples"][0])
        self.assertEqual(copied["samples"][1]["actors"][0]["logical"]["x"], 586)
        self.assertEqual(row["samples"][1]["actors"][0]["logical"]["x"], 585)

    def test_first_jump_must_land_before_second(self):
        instance = meter()
        with self.assertRaisesRegex(ValueError, "return to ground between jumps"):
            drive(instance, 2, 10, raised_valley=True)

    def test_finished_stock_command_can_precede_chill_by_one_update(self):
        instance = meter()
        drive(instance, 2, 10, handoff_delay=1)
        self.assertEqual(instance.outcomes[2]["terminalHandoffFrame"], 18)
        self.assertEqual(instance.outcomes[2]["releasedFrame"], 19)
        for changes in ({"handoff_delay": 2}, {"expired_jump": True}):
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "authored timer"):
                drive(meter(), 2, 10, **changes)

    def test_independent_effect_choices_need_exact_visible_jump_outputs(self):
        with self.assertRaisesRegex(ValueError, "effect output differs"):
            drive(meter(), 1, 10, heart=True, missing_heart=True)
        with self.assertRaisesRegex(ValueError, "effect output differs"):
            drive(meter(), 1, 10, unexpected_heart=True)
        with self.assertRaisesRegex(ValueError, "another Pokemon cry"):
            drive(meter(), 1, 10, cry=True, wrong_cry=True)

    def test_stock_heart_can_stay_visible_across_both_jumps(self):
        instance = meter()
        drive(instance, 2, 10, heart=True, continued_heart=True)
        self.assertEqual(len(instance.outcomes[2]["heartDraws"]), 2)

    def test_prior_admitted_heart_needs_a_current_jump_draw(self):
        instance = meter()
        drive(instance, 1, 10, heart=True)
        drive(instance, 2, 20, heart=True, existing_heart=True)
        self.assertEqual([s["heart"][0]["returnValue"]
                          for s in instance.outcomes[2]["stepEvents"].values()], [0, 0])
        with self.assertRaisesRegex(ValueError, "heart was not visibly admitted"):
            drive(meter(), 1, 10, heart=True, existing_heart=True)
        with self.assertRaisesRegex(ValueError, "heart was not visibly admitted"):
            drive(instance, 1, 40, heart=True, existing_heart=True, hidden_heart=True)

    def test_hidden_stock_heart_cannot_earn_visible_jump_credit(self):
        with self.assertRaisesRegex(ValueError, "heart was not visibly admitted"):
            drive(meter(), 2, 10, heart=True, continued_heart=True, hidden_heart=True)

    def test_wrong_count_and_overlap_reject(self):
        instance = meter()
        sample = frame(10)
        public = select_current_actor(sample, sample["actors"][0])
        request = bytearray(28)
        request[:4] = b"\x01\x00\x1c\x00"
        request[8:10] = b"\x00\x04"
        response = bytearray(request)
        response[22] = 1
        response[23] = 3
        event = dict(kind="native-observation", data=dict(observation="walk-policy", operation=4,
                     returnValue=1,
                     slot=0, publicSubject=public, publicSubjectAfter=public,
                     requestHex=request.hex(), responseHex=response.hex()))
        with self.assertRaisesRegex(ValueError, "count overlaps"):
            instance._policy(event, sample, sample["actors"][0], None)
        response[23] = 1
        event["data"]["responseHex"] = response.hex()
        instance.pending = selected(1, 9)
        with self.assertRaisesRegex(ValueError, "count overlaps"):
            instance._policy(event, sample, sample["actors"][0], None)

    def test_native_selection_uses_exact_profile_and_two_draws(self):
        instance = meter()
        sample = frame(10)
        sample["nativeObservation"] = dict(coverageComplete=True, profilesEvicted=0,
                                            profileFingerprints=[1234])
        public = select_current_actor(sample, sample["actors"][0])
        request = bytearray(28)
        request[:4] = b"\x01\x00\x1c\x00"
        request[8:10] = b"\x00\x04"
        response = bytearray(request)
        response[22:24] = b"\x01\x02"
        lane = bytearray(80)
        lane[31], lane[43], lane[57], lane[67], lane[75] = 1, 100, 0x90, 60, 0x80
        resolved = bytearray(216)
        resolved[:80] = lane
        struct.pack_into("<I", resolved, 192, 1234)
        resolved[196:210] = bytes(12) + b"\x01\x00"
        resolved[212] = APPLICATION_LOCAL
        struct.pack_into("<H", resolved, 214, PLAYER_CONDITION)
        cache = dict(frame=10, nativeCycle=1010,
                     resolvedProfiles=[dict(resolved=True, fingerprint=1234,
                                            sourceSha256=SOURCE["profileSha256"], resultHex=resolved.hex())])
        event = dict(kind="native-observation", data=dict(observation="walk-policy", operation=4,
                     returnValue=1, slot=0, publicSubject=public, publicSubjectAfter=public,
                     requestHex=request.hex(), responseHex=response.hex(), laneHex=lane.hex(),
                     rngReturns=[dict(value=0), dict(value=0)]))
        instance._policy(event, sample, sample["actors"][0], cache)
        self.assertEqual(instance.pending["count"], 2)
        instance.pending = None
        event["data"]["rngReturns"][1]["value"] = 99
        with self.assertRaisesRegex(ValueError, "extra-hop draw differs"):
            instance._policy(event, sample, sample["actors"][0], cache)
        event["data"]["rngReturns"][1]["value"] = 0
        bad_cache = deepcopy(cache)
        bad = bytearray.fromhex(bad_cache["resolvedProfiles"][0]["resultHex"])
        bad[43] = 0
        bad_cache["resolvedProfiles"][0]["resultHex"] = bad.hex()
        with self.assertRaisesRegex(ValueError, "authored 60/50"):
            instance._policy(event, sample, sample["actors"][0], bad_cache)

    def test_while_true_playful_needs_parent_and_adjacent_same_target(self):
        instance = meter()
        first = frame(833)
        trigger = condition_event(first, truth=True, triggered=True, sequence=45)
        instance._condition(trigger, first)
        self.assertEqual(instance.active_condition["conditionId"], PLAYER_CONDITION)
        retained = frame(859)
        held = condition_event(retained, truth=True, triggered=False, sequence=68)
        instance._condition(held, retained)
        self.assertTrue(instance.active_condition["truth"])
        changed = deepcopy(held)
        changed["data"]["reasonId"] &= ~(1 << 13)
        with self.assertRaisesRegex(ValueError, "fresh activation lacks a true source"):
            instance._condition(changed, retained)
        for fault in ("parent", "distance"):
            sample = frame(860)
            if fault == "parent":
                sample["actors"][0]["matchedLayerMask"] &= ~(1 << FIND_APPLICATION_LOCAL)
            else:
                sample["player"]["y"] += 5
            with self.assertRaisesRegex(ValueError, "Find Playmate|far from"):
                instance._condition(condition_event(sample, truth=True, triggered=False, sequence=69), sample)

    def test_find_playmate_retains_its_own_timed_target(self):
        instance = meter()
        trigger = condition_event(frame(833), truth=True, triggered=True, sequence=45, until=785, find=True)
        instance._condition(trigger, frame(833))
        held = condition_event(frame(859), truth=False, triggered=False, sequence=68, until=785, find=True)
        instance._condition(held, frame(859))
        self.assertEqual(instance.find_condition["activeUntil"], 785)
        held["data"]["valueB"] += 1
        with self.assertRaisesRegex(ValueError, "exact fresh true activation"):
            instance._condition(held, frame(859))

    def test_stage_controls_change_the_sample_and_reject_it(self):
        for fault in ("missing-find-playmate", "far-playmate"):
            with self.subTest(fault=fault):
                instance = meter()
                sample = frame(833)
                event = condition_event(sample, truth=True, triggered=True, sequence=45)
                row = dict(phase="observe", events=[event], samples=[sample])
                negative = PlayfulHopNegative(fault)
                changed = negative.mutate(row, instance.subjects)
                self.assertTrue(negative.applied)
                self.assertEqual(changed["events"], row["events"])
                self.assertEqual(sample, frame(833))
                with self.assertRaisesRegex(ValueError, "Find Playmate|far from"):
                    instance._condition(event, changed["samples"][0])

    def test_false_first_activation_rejects_and_copied_fault_hits_source(self):
        instance = meter()
        first = frame(833)
        trigger = condition_event(first, truth=True, triggered=True, sequence=45)
        negative = PlayfulHopNegative("false-first-activation")
        mutated = negative.mutate(dict(phase="observe", events=[trigger], samples=[]), instance.subjects)
        self.assertTrue(negative.applied)
        with self.assertRaisesRegex(ValueError, "fresh activation lacks a true source"):
            instance._condition(mutated["events"][0], first)
        retained = condition_event(frame(859), truth=False, triggered=False, sequence=68)
        with self.assertRaisesRegex(ValueError, "fresh activation lacks a true source"):
            instance._condition(retained, frame(859))

    def test_false_first_activation_also_hits_a_setup_receipt(self):
        instance = meter()
        first = frame(833)
        trigger = condition_event(first, truth=True, triggered=True, sequence=45)
        negative = PlayfulHopNegative("false-first-activation")
        row = dict(phase="setup", action="spawn-clefairy",
                   receipt=dict(subject=dict(handle=instance.subjects["clefairy"]["handle"]),
                                events=[trigger]))
        changed = negative.mutate(row, {})
        self.assertTrue(negative.applied)
        with self.assertRaisesRegex(ValueError, "fresh activation lacks a true source"):
            instance._condition(changed["receipt"]["events"][0], first)

    def test_negative_names_stay_scoped(self):
        self.assertEqual(KIND, "playful-in-place-hop-v1")
        for name in ("wrong-count", "missing-second-hop", "overlap", "displacement",
                     "false-first-activation", "heart-draw", "cry-draw",
                     "heart-not-visible", "wrong-cry"):
            self.assertFalse(PlayfulHopNegative(name).applied)

    def test_copied_effect_faults_change_the_actual_native_receipt(self):
        owner = meter().subjects["clefairy"]["handle"]
        public = select_current_actor(frame(10), frame(10)["actors"][0])
        for name, observation, field in (
                ("heart-draw", "playful-sequence", "rngReturns"),
                ("cry-draw", "playful-sequence", "rngReturns"),
                ("heart-not-visible", "playful-heart", "returnValue"),
                ("wrong-cry", "playful-cry", "species")):
            data = dict(observation=observation, publicSubject=public,
                        rngReturns=[dict(value=10), dict(value=90)],
                        returnValue=1, species=35)
            row = dict(phase="observe", events=[dict(kind="native-observation", data=data)])
            fault = PlayfulHopNegative(name)
            changed = fault.mutate(row, {"clefairy": {"handle": owner}})
            self.assertTrue(fault.applied, name)
            self.assertNotEqual(changed["events"][0]["data"][field], data[field])


if __name__ == "__main__":
    unittest.main()
