"""Host controls for the data-only shared devtools test language."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from tools.overworld.devtools_test_contract import (
    HEIGHT_CONTROL, SPAWN_WORK_BUDGET, TestEvaluator, validate_test,
    _d1_warmup_initial, _d1_warmup_observe, _d1_warmup_arm,
    _d1_spawn_remaining_frames,
)


def recipe():
    return {"schemaVersion": 1, "id": "test.actor", "title": "Actor witness", "mode": "normal",
            "fixture": {"rom": "test.nds", "save": "test.sav"},
            "expectationSource": "documentation/overworld-system/verification.md",
            "requirements": [], "budgets": {"maxSeconds": 30, "maxFrames": 20,
                "noProgressFrames": 10, "minObservedFrames": 2},
            "subjects": [{"id": "subject", "species": 165, "role": "WILD", "acquire": "existing"}],
            "setup": [], "actions": [{"id": "sample", "op": "step", "args": {"frames": 2, "keys": []},
                "budget": {"maxSeconds": 10, "maxFrames": 2, "noProgressFrames": 2}}],
            "assertions": [{"kind": "actor-field", "subject": "subject", "path": "motionPhase",
                "operator": "eq", "value": "IDLE"}]}


def snapshot(frame=1):
    actor = {"handle": {"value": 65536, "slot": 0, "generation": 1, "fieldEpoch": 1,
                       "mapGeneration": 1, "encounterGeneration": 1},
             "subjectIdentity": 123, "species": 165, "role": "WILD", "active": True,
             "presentationAttached": True, "identityVerified": True,
             "authorityGeneration": 1, "engineAnchorGeneration": 1, "presentationGeneration": 1,
             "motionPhase": "IDLE", "commitSequence": 0}
    return {"frame": frame, "context": {"fieldEpoch": 1, "mapGeneration": 1},
            "actors": [actor], "player": {"x": 1, "y": 2}, "prepared": False}


def event(frame=1, name="MOTION_FINISHED", sequence=1):
    handle = snapshot()["actors"][0]["handle"]
    return {"frame": frame, "kind": "native", "data": {"traceStream": 1, "sequence": sequence,
        "actorHandle": handle["value"], "actor": {k: v for k, v in handle.items() if k != "value"},
        "event": name}}


class D1WarmupTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[2]
    names = ("population.spawn-work-budget", "world.unmounted.spawn-zero-stutter")

    def load(self, name):
        return json.loads((self.root / "tests/overworld/test-recipes" / (name + ".json")).read_text())

    def warmup(self):
        subject = {"active": True, "species": 56, "role": "FOLLOWER",
                   "subjectIdentity": 123, "identityVerified": True}
        current = {"frame": 1, "prepared": False, "fieldAvailable": True,
            "observationBoundary": "main-task-queue-completion",
            "fieldControl": {"taskPointer": 0}, "context": {"mapId": 67},
            "actors": [subject], "party": [{"species": 56, "personality": 123,
                "identityVerified": True, "hp": 15}],
            "nativeObservation": {"playerStepCount": 0, "coverageComplete": True,
                "error": None, "eventsDropped": 0}, "selector": {"physicalPressed": 0},
            "player": {"x": 564, "y": 392}}
        initial = deepcopy(current)
        rows = []
        for dx, dy, tiles, direction in ((1, 0, 1, 3), (0, 1, 6, 1),
                                         (1, 0, 20, 3), (0, 1, 8, 1)):
            for _ in range(tiles):
                origin = [current["player"]["x"], current["player"]["y"]]
                target = [origin[0] + dx, origin[1] + dy]
                count = len(rows) + 1
                data = {"observation": "player-step-admitted", "setupMode": "normal",
                    "stepIndex": count, "mapId": 67 if origin[0] < 576 else 33,
                    "direction": direction, "origin": origin, "target": target,
                    "objectBefore": dict(x=origin[0], y=origin[1]),
                    "objectAfter": dict(x=target[0], y=target[1]),
                    "objectPointer": 100, "returnValue": 100}
                current["frame"] += 1
                current["context"]["mapId"] = 67 if target[0] < 576 else 33
                current["player"].update(x=target[0], y=target[1])
                current["nativeObservation"]["playerStepCount"] = count
                rows.append((deepcopy(current), [{"kind": "native-observation", "data": data}]))
        current["player"].update(x_prev=585, y_prev=406, flags=1, movement_cmd=1,
            pos_x=585 * 65536 + 32768, pos_z=406 * 65536 + 32768, unk88_y=0)
        return initial, rows, current, subject

    def replay(self, initial, rows):
        state = _d1_warmup_initial(initial)
        for current, events in rows:
            _d1_warmup_observe(state, current, events)
        return state

    def test_both_recipe_routes_release_at_admission_then_require_exact_ground(self):
        registry = json.loads((self.root / "tools/overworld/runtime_proof_registry.json").read_text())["sharedTests"]
        for name in self.names:
            with self.subTest(name=name):
                data = self.load(name); value = validate_test(data)
                prefix = [a["args"]["until"]["value"] for a in value["setup"] if a["op"] == "step" and "until" in a["args"]]
                self.assertEqual(prefix, [1, 7, 27, 35])
                stops = [a["args"]["until"] for a in value["actions"] if "until" in a["args"]]
                settles = [a for a in value["actions"] if a["id"].endswith("-settle")]
                endpoints = [a["args"]["predicate"] for a in settles]
                self.assertTrue(all(p["kind"] == "player-field" for p in stops))
                self.assertEqual([(p["path"], p["value"]) for p in stops[:5]],
                                 [("y", 398), ("x", 565), ("y", 393), ("x", 543), ("y", 402)])
                self.assertEqual([(p["map"], p["x"], p["z"]) for p in endpoints[:5]],
                    [(33, 585, 398), (67, 565, 398), (67, 565, 393),
                     (67, 543, 393), (67, 543, 402)])
                self.assertEqual(len(stops), len(endpoints))
                self.assertTrue(all(a["budget"] == {"maxSeconds": 10, "maxFrames": 16,
                                                   "noProgressFrames": 8} for a in settles))
                for move, point in zip((a for a in value["actions"] if "until" in a["args"]), endpoints):
                    axis = "y" if move["args"]["keys"][0] in ("UP", "DOWN") else "x"
                    self.assertEqual(move["args"]["until"], {"kind": "player-field", "path": axis,
                        "operator": "eq", "value": point["z" if axis == "y" else "x"], "when": "final"})
                if name == self.names[0]:
                    self.assertEqual(len(stops), 5)
                    self.assertEqual([a["args"]["frames"] for a in value["actions"] if "until" in a["args"]],
                                     [64, 128, 64, 128, 64])
                else:
                    self.assertEqual(len(stops), 63)
                    self.assertEqual(endpoints[-1], {"kind": "player-settled-at", "map": 67,
                                                    "x": 555, "z": 393, "when": "final"})
                    self.assertTrue(all(a["args"]["frames"] == 256 for a in value["actions"]
                                        if "until" in a["args"]))
                path = self.root / "tests/overworld/test-recipes" / (name + ".json")
                self.assertEqual(registry[name]["recipeSha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_wrong_prefix_and_changed_ground_stops_are_rejected(self):
        for name in self.names:
            for fault in ("direction", "prefix-count", "settle", "skip", "endpoint", "old-counter-stop", "missing-finish"):
                data = self.load(name)
                if fault == "direction": data["setup"][1]["args"]["keys"] = ["LEFT", "B"]
                elif fault == "prefix-count": data["setup"][1]["args"]["until"]["value"] = 2
                elif fault == "settle": data["setup"][2]["args"]["predicate"]["x"] = 566
                elif fault == "skip": data["setup"][1]["skipIf"] = {"kind": "player-settled-at", "map": 67, "x": 565, "z": 392}
                elif fault == "endpoint": data["actions"][1]["args"]["predicate"]["z"] = 399
                elif fault == "missing-finish": del data["actions"][1]
                else: data["actions"][0]["args"]["until"] = {
                    "kind": "player-step-count", "operator": "eq", "value": 43}
                with self.subTest(name=name, fault=fault), self.assertRaises(ValueError): validate_test(data)

    def test_measured_admission_releases_before_completed_held_key_repeats(self):
        evaluator = TestEvaluator(self.load(self.names[0]))
        move, settle = evaluator.test["actions"][:2]
        # Copied native states from test-af6fd...: UP admission934, finish937,
        # then stale heldUP admission938 despite the new physical LEFT key.
        admitted = {"frame": 934, "observationBoundary": "main-task-queue-completion",
            "context": {"mapId": 33}, "fieldControl": {"taskPointer": 0},
            "player": dict(x=585, y=398, x_prev=585, y_prev=399, pos_x=38371328,
                pos_z=26165248, unk88_y=0, movement_cmd=88, flags=0x2000E411)}
        finished = deepcopy(admitted)
        finished["frame"] = 937
        finished["player"].update(y_prev=398, pos_z=26116096, flags=0x2000E431)
        overshot = deepcopy(admitted)
        overshot["frame"] = 938
        overshot["player"].update(y=397, y_prev=398, pos_z=26099712)
        self.assertTrue(evaluator.check(move["args"]["until"], admitted))
        self.assertFalse(evaluator.check(settle["args"]["predicate"], admitted))
        self.assertTrue(evaluator.check(settle["args"]["predicate"], finished))
        self.assertFalse(evaluator.check(move["args"]["until"], overshot))
        self.assertFalse(evaluator.check(settle["args"]["predicate"], overshot))

    def test_spawn_final_wait_keeps_exact_entry_stop_and_bounds(self):
        data = self.load(self.names[0])
        value = validate_test(data)
        self.assertEqual(value["actions"][-1], {
            "id": "finish-natural-entry", "op": "wait",
            "args": {"predicate": {"kind": "measurement-stage",
                "measurement": SPAWN_WORK_BUDGET, "stage": "complete",
                "when": "final"}},
            "budget": {"maxSeconds": 60, "maxFrames": 256,
                       "noProgressFrames": 32},
        })
        self.assertEqual(value["budgets"], {"maxSeconds": 180, "maxFrames": 720,
            "noProgressFrames": 320, "minObservedFrames": 120})
        for fault in ("frames", "stall", "seconds", "predicate", "name",
                      "order", "missing", "duplicate", "skip", "global"):
            changed = deepcopy(data)
            wait = changed["actions"][-1]
            if fault == "frames": wait["budget"]["maxFrames"] = 257
            elif fault == "stall": wait["budget"]["noProgressFrames"] = 31
            elif fault == "seconds": wait["budget"]["maxSeconds"] = 61
            elif fault == "predicate": wait["args"]["predicate"] = {
                "kind": "measurement-complete", "measurement": SPAWN_WORK_BUDGET}
            elif fault == "name": wait["id"] = "unchecked-entry-wait"
            elif fault == "order": changed["actions"][-2:] = changed["actions"][-2:][::-1]
            elif fault == "missing": changed["actions"].pop()
            elif fault == "duplicate": changed["actions"].append(deepcopy(wait))
            elif fault == "skip": wait["skipIf"] = {
                "kind": "actor-present", "subject": "mankey"}
            else: changed["budgets"]["maxFrames"] = 721
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                validate_test(changed)

    def test_spawn_pre_crossing_idle_keeps_exact_neutral_input(self):
        data = self.load(self.names[0])
        value = validate_test(data)
        self.assertEqual(value["actions"][2], {
            "id": "route-up-scan-idle", "op": "step",
            "args": {"frames": 36, "keys": []},
            "budget": {"maxSeconds": 10, "maxFrames": 36,
                       "noProgressFrames": 36}})
        for fault in ("keys", "frames"):
            changed = deepcopy(data)
            if fault == "keys": changed["actions"][2]["args"]["keys"] = ["UP"]
            else: changed["actions"][2]["args"]["frames"] = 35
            with self.subTest(fault=fault), self.assertRaisesRegex(
                    ValueError, "spawn-work pre-crossing idle differs"):
                validate_test(changed)

    def test_spawn_actual_setup_frames_keep_the_same_overall_bound(self):
        evaluator = TestEvaluator(self.load(self.names[0]))
        evaluator.install_measurements({SPAWN_WORK_BUDGET: {"schema": {}, "sourceSha256": "a" * 64}})
        self.assertEqual(evaluator.test["budgets"]["maxFrames"], 720)
        self.assertEqual(evaluator.measurements[SPAWN_WORK_BUDGET].max_frames, 720)
        initial, rows, terminal, subject = self.warmup()
        state = self.replay(initial, rows)
        for frame in range(rows[-1][0]["frame"] + 1, 165):
            terminal["frame"] = frame
            _d1_warmup_observe(state, terminal, [])
        _d1_warmup_arm(state, terminal, subject)
        remaining = _d1_spawn_remaining_frames(state, terminal, 163, 720)
        self.assertEqual(remaining, 557)
        # Retained3577: setup163 + observed481 =644, not the old720 cap.
        self.assertEqual(163 + 481, 644)
        self.assertEqual(remaining - 481, 76)
        self.assertEqual(163 + remaining, 720)
        for used in (0, 240, 719):
            current = {"frame": initial["frame"] + used}
            self.assertEqual(_d1_spawn_remaining_frames(state, current, used, 720), 720 - used)

    def test_spawn_setup_accounting_rejects_missing_duplicate_or_changed_boundaries(self):
        initial, rows, terminal, _ = self.warmup()
        state = self.replay(initial, rows)
        terminal["frame"] = initial["frame"] + 163
        for count in (162, 164, True, None, -1, 720):
            with self.subTest(count=count), self.assertRaisesRegex(ValueError, "completed-frame accounting"):
                _d1_spawn_remaining_frames(state, terminal, count, 720)
        for fault in ("missing-initial", "missing-terminal", "backward", "grown-cap"):
            copied_state, copied = deepcopy(state), deepcopy(terminal)
            if fault == "missing-initial": copied_state.pop("initialFrame")
            elif fault == "missing-terminal": copied.pop("frame")
            elif fault == "backward": copied["frame"] = initial["frame"] - 1
            with self.subTest(fault=fault), self.assertRaisesRegex(ValueError, "completed-frame accounting"):
                _d1_spawn_remaining_frames(copied_state, copied, 163, 721 if fault == "grown-cap" else 720)

    def test_native_route_reaches_exact_arm_without_preparation(self):
        initial, rows, terminal, subject = self.warmup()
        state = self.replay(initial, rows)
        _d1_warmup_arm(state, terminal, subject)
        self.assertEqual(state["count"], 35)

    def test_moving_follower_at873_can_bind_but_moving_player_at879_cannot(self):
        initial, rows, terminal, subject = self.warmup()
        state = self.replay(initial, rows)
        # Public pose values retained from the real failed zero-stutter run.
        terminal["frame"] = 873
        terminal["player"].update(flags=537977905, movement_cmd=1,
            pos_x=38371328, pos_z=26640384)
        terminal["actors"][0]["motionPhase"] = "MOVING"
        _d1_warmup_arm(state, terminal, subject)
        data = self.load(self.names[1])
        self.assertEqual(validate_test(data)["setup"][-2]["args"]["predicate"],
            {"kind": "actor-present", "subject": "mankey", "when": "final"})
        copied = deepcopy(terminal)
        copied["frame"] = 879
        copied["actors"][0]["motionPhase"] = "IDLE"
        copied["player"].update(flags=537977873, movement_cmd=62, pos_x=38376369)
        with self.assertRaisesRegex(ValueError, "did not finish the exact normal35-step route"):
            _d1_warmup_arm(state, copied, subject)

    def test_counter_cannot_replace_a_missing_native_step(self):
        initial, rows, _, _ = self.warmup()
        rows[0] = (rows[0][0], [])
        with self.assertRaisesRegex(ValueError, "counter lacks its exact native admissions"):
            self.replay(initial, rows)

    def test_wrong_native_direction_and_counter_reset_are_rejected(self):
        for fault in ("direction", "counter"):
            initial, rows, _, _ = self.warmup()
            if fault == "direction": rows[0][1][0]["data"]["direction"] = 2
            else: rows[0][0]["nativeObservation"]["playerStepCount"] = 0
            with self.subTest(fault=fault), self.assertRaisesRegex(ValueError, "native admission"):
                self.replay(initial, rows)

    def test_preparation_identity_change_and_false_terminal_are_rejected(self):
        for fault in ("prepared", "identity", "terminal"):
            initial, rows, terminal, subject = self.warmup()
            if fault == "prepared": rows[0][0]["prepared"] = True
            elif fault == "identity": rows[0][0]["actors"][0]["subjectIdentity"] = 456
            else: terminal["player"]["pos_z"] -= 32768
            with self.subTest(fault=fault), self.assertRaises(ValueError):
                state = self.replay(initial, rows)
                _d1_warmup_arm(state, terminal, subject)


class ContractTests(unittest.TestCase):
    def test_spawn_binding_excludes_rebound_initial_actor_and_uses_height_receipt(self):
        value = recipe()
        value["subjects"] = [{"id": "subject", "species": 165,
                              "role": "WILD", "acquire": "spawn"}]
        evaluator = TestEvaluator(value)
        initial = snapshot()
        evaluator.observe(initial, count_frame=False)

        rebound = deepcopy(initial["actors"][0])
        rebound["handle"] = {**rebound["handle"], "value": 65536,
                             "fieldEpoch": 2, "mapGeneration": 2}
        fresh = deepcopy(rebound)
        fresh["handle"] = {**fresh["handle"], "value": 65537, "slot": 1}
        fresh["subjectIdentity"] = 456
        other = deepcopy(fresh)
        other["handle"] = {**other["handle"], "value": 65538, "slot": 2}
        other["subjectIdentity"] = 789
        current = {**snapshot(2), "actors": [rebound, fresh, other],
                   "context": {"fieldEpoch": 2, "mapGeneration": 2}}
        evaluator.first_handles = set()
        evaluator.measurements[HEIGHT_CONTROL] = SimpleNamespace(
            result=lambda: {"subject": fresh})

        self.assertEqual(evaluator._candidates("subject", current), [fresh, other])
        self.assertTrue(evaluator.check(
            {"kind": "actor-present", "subject": "subject"}, current))
        evaluator.events[(tuple(fresh["handle"][key] for key in
                          ("value", "slot", "generation", "fieldEpoch",
                           "mapGeneration", "encounterGeneration")),
                          "ACTOR_ATTACHED")] = 1
        self.assertEqual(evaluator.bind("subject", current)["handle"], fresh["handle"])

    def test_host_hitch_continuation_is_diagnostic_only(self):
        path = Path(__file__).resolve().parents[2] / "tests/overworld/test-recipes/world.unmounted.long-travel-cadence.json"
        value = json.loads(path.read_text())
        value.update(requirements=[], diagnosticContinueHostHitches=True)
        diagnostic = json.loads(path.with_name("diagnostic.unmounted.host-hitch-followthrough.json").read_text())
        for key in value.keys() | diagnostic.keys():
            if key not in ("id", "title"):
                self.assertEqual(value.get(key), diagnostic.get(key), key)
        self.assertTrue(validate_test(value)["diagnosticContinueHostHitches"])
        for change in ({"mode": "normal"}, {"requirements": ["legacy.unmounted-long-travel"]},
                       {"diagnosticContinueHostHitches": 1}, {"diagnosticContinueHostHitches": False},
                       {"measurements": []}):
            with self.assertRaises(ValueError):
                validate_test({**value, **change})
        from tools.overworld.control import _finalize_shared_test_scoped
        result = _finalize_shared_test_scoped(value, {"passed": True, "acceptedProof": True,
            "fixtureProof": {"proofInputs": {"schema": "untrusted"}}})
        self.assertFalse(result["passed"])
        self.assertFalse(result["acceptedProof"])
        self.assertFalse(result["proofAcceptance"]["eligible"])

    def test_spawn_cost_experiment_cannot_claim_requirements(self):
        value = recipe()
        value.update(mode="prepared", spawnObserverCost="baseline")
        self.assertEqual(validate_test(value)["spawnObserverCost"], "baseline")
        normal = {**value, "mode": "normal"}
        self.assertEqual(validate_test(normal)["spawnObserverCost"], "baseline")
        for change in ({"mode": "observer-control"}, {"requirements": ["anything"]},
                       {"mode": "normal", "spawnObserverCost": "omit-spawn-details"},
                       {"spawnObserverCost": "arbitrary"}):
            with self.assertRaises(ValueError):
                validate_test({**value, **change})
        from tools.overworld.control import finalize_shared_test
        for test, record in ((value, {"passed": True}), (normal, {"passed": True}),
                             (recipe(), {"passed": True, "observationSetup": {"spawnObserverCost": {}}})):
            self.assertFalse(finalize_shared_test(test, record)["acceptedProof"])

    def test_prebind_idle_count_uses_current_verified_actor(self):
        predicate = {"kind": "actor-count", "subject": "subject", "operator": "eq",
                     "value": 1, "motionPhase": "IDLE"}
        value = recipe()
        value["assertions"] = [predicate]
        evaluator = TestEvaluator(value)
        sample = snapshot()
        evaluator.latest = sample
        self.assertTrue(evaluator.check(predicate))
        sample["actors"][0]["motionPhase"] = "ADVANCING"
        self.assertFalse(evaluator.check(predicate))
        sample["actors"][0]["motionPhase"] = "IDLE"
        sample["actors"][0]["identityVerified"] = False
        with self.assertRaises(ValueError):
            evaluator.check(predicate)
        sample["actors"][0]["identityVerified"] = True
        del sample["actors"][0]["motionPhase"]
        with self.assertRaises(ValueError):
            evaluator.check(predicate)

    def test_idle_count_rejects_unknown_phase_filter(self):
        for phase in (None, True, "", "ANY", "ADVANCING"):
            value = recipe()
            value["assertions"] = [{"kind": "actor-count", "subject": "subject",
                "operator": "eq", "value": 1, "motionPhase": phase}]
            with self.subTest(phase=phase), self.assertRaises(ValueError):
                validate_test(value)

    def test_normal_ledyba_contract_keeps_long_actor_scoped_wait(self):
        root = Path(__file__).resolve().parents[2]
        path = root / "tests/overworld/test-recipes/chain.ledyba-witness.json"
        value = validate_test(json.loads(path.read_text()))
        scenario = json.loads((root / "tests/overworld/scenarios/chain.pause.ledyba-normal-profile.json").read_text())
        entry = json.loads((root / "tools/overworld/runtime_proof_registry.json").read_text())["sharedTests"][value["id"]]
        self.assertEqual(value["budgets"]["minObservedFrames"], 5000)
        self.assertEqual(scenario["adapter"]["minimumFrames"], 5000)
        self.assertEqual(entry["minimumObservedFrames"], 5000)
        self.assertEqual(entry["recipeSha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        wait = value["actions"][-1]
        self.assertEqual(wait["args"]["predicate"]["kind"], "measurement-complete")
        self.assertEqual(wait["budget"]["noProgressFrames"], 240)
        self.assertEqual(value["budgets"]["noProgressFrames"], 240)
        self.assertEqual(value["requirements"], ["legacy.ledyba-normal-profile"])
        self.assertEqual(scenario["capture"], "none")

    def test_ready_measurement_waits_for_bound_subject_frame_floor(self):
        value = recipe()
        value["budgets"].update(maxFrames=6000, minObservedFrames=5000)
        evaluator = TestEvaluator(value)
        evaluator.latest = snapshot()
        evaluator.measurements["ledyba-chain-v1"] = SimpleNamespace(result=lambda: {"ready": True})
        predicate = {"kind": "measurement-complete", "measurement": "ledyba-chain-v1"}
        for observed in (0, 4999):
            evaluator.frames = observed
            self.assertFalse(evaluator.check(predicate))
        evaluator.frames = 5000
        self.assertTrue(evaluator.check(predicate))
        evaluator.measurements["ledyba-chain-v1"] = SimpleNamespace(result=lambda: {"ready": False})
        self.assertFalse(evaluator.check(predicate))

    def test_literal_recipe_round_trip(self):
        value = recipe()
        self.assertEqual(validate_test(value)["id"], value["id"])

    def test_unknown_actions_private_oracles_and_unbounded_work_rejected(self):
        for edit in (
            lambda t: t["actions"][0].update(op="python"),
            lambda t: t["actions"][0].pop("budget"),
            lambda t: t["assertions"][0].update(path="movementPolicy.chainCount"),
            lambda t: t["budgets"].update(maxFrames=True),
            lambda t: t.update(unknown=True),
        ):
            value = recipe(); edit(value)
            with self.subTest(value=value), self.assertRaises(ValueError): validate_test(value)

    def test_normal_prepared_attempt_rejected(self):
        value = recipe()
        value["setup"] = [{"id": "teleport", "op": "teleport", "args": {"map": 33, "x": 1, "z": 2},
                            "budget": {"maxSeconds": 10, "maxFrames": 10, "noProgressFrames": 10}}]
        with self.assertRaises(ValueError): validate_test(value)
        value["mode"] = "prepared"
        self.assertEqual(validate_test(value)["setup"][0]["op"], "teleport")

    def test_no_empty_proof(self):
        value = recipe(); value["assertions"] = []
        with self.assertRaises(ValueError): validate_test(value)

    def test_tools_only_frame_test_needs_no_invented_actor(self):
        value = recipe(); value["subjects"] = []
        value["assertions"] = [{"kind": "frame-count", "operator": "gte", "value": 2}]
        evaluator = TestEvaluator(value)
        evaluator.observe(snapshot(1)); evaluator.observe(snapshot(2))
        result = evaluator.finish()
        self.assertTrue(result["passed"])
        self.assertEqual(result["subjects"], {})
        self.assertFalse(result["acceptedProof"])
        value["requirements"] = ["shared.actor-identity.prepared-v1"]
        with self.assertRaises(ValueError): validate_test(value)

    def test_unique_action_ids_and_known_subjects(self):
        value = recipe(); value["actions"].append(deepcopy(value["actions"][0]))
        with self.assertRaises(ValueError): validate_test(value)

    def test_setup_skip_is_typed_and_cannot_skip_observation(self):
        value = recipe()
        action = deepcopy(value["actions"][0]); action["id"] = "route"
        action["skipIf"] = {"kind": "actor-present", "subject": "subject"}
        value["setup"] = [action]
        self.assertEqual(validate_test(value)["setup"][0]["skipIf"]["kind"], "actor-present")
        invalid = deepcopy(value); invalid["actions"][0]["skipIf"] = action["skipIf"]
        with self.assertRaises(ValueError): validate_test(invalid)
        invalid = deepcopy(value); invalid["setup"][0]["op"] = "bind"
        invalid["setup"][0]["args"] = {"subject": "subject"}
        with self.assertRaises(ValueError): validate_test(invalid)

    def test_step_until_uses_the_same_typed_predicate_validation(self):
        value = recipe(); value["actions"][0]["args"]["until"] = {
            "kind": "player-field", "path": "x", "operator": "eq", "value": 3}
        self.assertEqual(validate_test(value)["actions"][0]["args"]["until"]["value"], 3)
        value["actions"][0]["args"]["until"]["path"] = "private.scriptFlags"
        with self.assertRaises(ValueError): validate_test(value)
        value = recipe(); value["assertions"][0]["subject"] = "unknown"
        with self.assertRaises(ValueError): validate_test(value)


class EvaluatorTests(unittest.TestCase):
    def evaluator(self):
        evaluator = TestEvaluator(recipe())
        evaluator.bind("subject", snapshot())
        evaluator.observe(snapshot())
        return evaluator

    def test_exact_subject_and_two_frames_required(self):
        evaluator = self.evaluator()
        self.assertFalse(evaluator.finish()["passed"])
        evaluator = self.evaluator(); evaluator.observe(snapshot(2))
        self.assertTrue(evaluator.finish()["passed"])
        self.assertFalse(evaluator.result()["acceptedProof"])

    def test_absent_wrong_role_and_stale_subject_cannot_pass(self):
        for field, value in (("species", 56), ("role", "FOLLOWER"), ("identityVerified", False),
                             ("presentationAttached", False), ("subjectIdentity", 124)):
            evaluator = self.evaluator(); current = snapshot(2); current["actors"][0][field] = value
            evaluator.observe(current)
            with self.subTest(field=field): self.assertFalse(evaluator.finish()["passed"])
        evaluator = self.evaluator(); current = snapshot(2); current["actors"] = []
        evaluator.observe(current); self.assertFalse(evaluator.finish()["passed"])

    def test_duplicate_or_missing_frames_fail_closed(self):
        for frame in (1, 3):
            evaluator = self.evaluator(); evaluator.observe(snapshot(frame))
            with self.subTest(frame=frame): self.assertFalse(evaluator.finish()["passed"])

    def test_first_failure_is_immutable_and_cannot_be_erased_by_later_good_data(self):
        evaluator = self.evaluator(); evaluator.fail("bad-motion", "bad completed motion", {"x": 1})
        prior = evaluator.result(); prior["failures"][0]["code"] = "modified"
        evaluator.observe(snapshot(2))
        self.assertEqual(evaluator.finish()["failures"][0]["code"], "bad-motion")
        self.assertFalse(evaluator.result()["passed"])

    def test_trace_gap_fails_but_normal_ring_wrap_is_not_unread_loss(self):
        evaluator = self.evaluator()
        evaluator.observe(snapshot(2), [{"frame": 2, "kind": "trace-status", "data": {
            "code": "unread-events-lost", "coverageComplete": False}}])
        self.assertFalse(evaluator.finish()["passed"])
        evaluator = self.evaluator()
        evaluator.observe(snapshot(2), [{"frame": 2, "kind": "trace-status", "data": {
            "code": "ring-overwrite", "unreadEventsLost": 0}}])
        self.assertTrue(evaluator.finish()["passed"])

    def test_event_count_bound_to_same_full_handle(self):
        evaluator = self.evaluator(); current = event(2); current["data"]["actor"]["mapGeneration"] = 2
        evaluator.observe(snapshot(2), [current])
        predicate = {"kind": "event-count", "subject": "subject", "event": "MOTION_FINISHED",
                     "operator": "gte", "value": 1}
        self.assertFalse(evaluator.check(predicate))
        evaluator = self.evaluator(); evaluator.observe(snapshot(2), [event(2)])
        self.assertTrue(evaluator.check(predicate))

    def test_pending_count_is_not_permanent_failure_but_forbidden_event_is(self):
        value = recipe(); value["assertions"].append({"kind": "event-count", "subject": "subject",
            "event": "MOTION_FINISHED", "operator": "gte", "value": 1})
        evaluator = TestEvaluator(value); evaluator.bind("subject", snapshot()); evaluator.observe(snapshot())
        self.assertEqual(evaluator.result()["failures"], [])
        evaluator.observe(snapshot(2), [event(2)])
        self.assertTrue(evaluator.finish()["passed"])
        value["assertions"][-1].update(event="MOTION_CANCELED", operator="eq", value=0, when="always")
        evaluator = TestEvaluator(value); evaluator.bind("subject", snapshot()); evaluator.observe(snapshot())
        evaluator.observe(snapshot(2), [event(2, "MOTION_CANCELED")])
        self.assertEqual(evaluator.result()["state"], "failed")

    def test_prepared_snapshot_taints_normal_run(self):
        evaluator = self.evaluator(); current = snapshot(2); current["prepared"] = True
        evaluator.observe(current); self.assertFalse(evaluator.finish()["passed"])

    def test_never_bound_subject_cannot_pass(self):
        evaluator = TestEvaluator(recipe()); evaluator.observe(snapshot()); evaluator.observe(snapshot(2))
        self.assertFalse(evaluator.finish()["passed"])

    def test_actual_public_duration_names_and_large_error_do_not_hide_failure(self):
        evaluator = self.evaluator(); current = snapshot(2)
        current["actors"][0].update(motionElapsed=3, motionDuration=8)
        current["player"].update(movement_cmd=0, movement_step=1)
        self.assertTrue(evaluator.check({"kind": "actor-field", "subject": "subject",
            "path": "motionDuration", "operator": "eq", "value": 8}, current))
        self.assertTrue(evaluator.check({"kind": "player-field", "path": "movement_cmd",
            "operator": "eq", "value": 0}, current))
        evaluator.fail("native-timeout", "original failure", {"large": "x" * 70000})
        self.assertEqual(evaluator.result()["failures"][0]["code"], "native-timeout")
        self.assertTrue(evaluator.result()["failures"][0]["details"]["omitted"])

    def test_spawn_acquisition_needs_new_handle_and_actual_attach(self):
        value = recipe(); value["subjects"][0]["acquire"] = "spawn"
        evaluator = TestEvaluator(value); initial = snapshot(); initial["actors"] = []
        evaluator.observe(initial); evaluator.observe(snapshot(2))
        with self.assertRaises(ValueError): evaluator.bind("subject", snapshot(2))
        evaluator = TestEvaluator(value); evaluator.observe(initial)
        evaluator.observe(snapshot(2), [event(2, "ACTOR_ATTACHED")])
        self.assertTrue(evaluator.bind("subject", snapshot(2))["identityVerified"])

    def test_setup_and_unbound_frames_have_no_live_observation_credit(self):
        evaluator = TestEvaluator(recipe())
        evaluator.observe(snapshot(), count_frame=False)
        evaluator.observe(snapshot(2))
        self.assertEqual(evaluator.result()["observedFrames"], 0)
        evaluator.bind("subject", snapshot(2))
        evaluator.observe(snapshot(3), count_frame=False)
        self.assertEqual(evaluator.result()["observedFrames"], 0)
        evaluator.observe(snapshot(4))
        self.assertEqual(evaluator.result()["observedFrames"], 1)

    def test_actor_count_waits_without_binding_absent_or_invalid_actor(self):
        evaluator = TestEvaluator(recipe()); current = snapshot(); current["actors"] = []
        predicate = {"kind": "actor-count", "subject": "subject", "operator": "gte", "value": 1}
        self.assertFalse(evaluator.check(predicate, current))
        self.assertTrue(evaluator.check(predicate, snapshot()))
        self.assertEqual(evaluator.subjects, {})
        current = snapshot(); current["actors"][0]["identityVerified"] = False
        with self.assertRaises(ValueError): evaluator.check(predicate, current)


class RamLedgeAuxiliaryFollowerTests(unittest.TestCase):
    def test_ledge_fault_uses_typed_leaf_guard_not_outer_failure_keys(self):
        from tools.overworld.devtools_ram_ledge_proof import validate_negative_result
        kind = "ram-ledge-continuity-v1"
        guards = {
            "stale-owner": "selected handle must name exactly one current active actor",
            "early-end": "Ram ended across a successful ledge",
            "reset": "Ram reset momentum before Crash",
            "turned-hop": "Ram ledge did not keep its South heading",
            "missing-commit": "profile feature did not complete",
            "crash": "Ram ledge canceled or published Crash",
        }
        for name, message in guards.items():
            with self.subTest(fault=name):
                result = {"passed": False,
                    "failures": [{"code": "measurement-failed", "message": kind}],
                    "measurements": {kind: {"passed": False, "failures": [message]}}}
                validate_negative_result(result, kind + ":" + name)
                wrong = deepcopy(result)
                wrong["measurements"][kind]["failures"] = ["a different guard"]
                with self.assertRaises(ValueError):
                    validate_negative_result(wrong, kind + ":" + name)
                absent = deepcopy(result)
                absent["measurements"] = {}
                with self.assertRaises(ValueError):
                    validate_negative_result(absent, kind + ":" + name)

    def fixture(self, kind='ram-ledge-continuity-v1'):
        root=Path(__file__).resolve().parents[2]
        case='profile.ram.behind-entry' if kind=='ram-behind-entry-v1' else 'profile.ram.ledge-continuity'
        data=json.loads((root/'tests/overworld/test-recipes'/f'{case}.json').read_text())
        action=next(a for a in data['setup'] if a['op']=='spawn' and a['args']['role']=='follower')
        level=action['args']['level']
        evaluator=TestEvaluator(data);evaluator.install_measurements({kind:{'contractVersion':1}})
        initial=snapshot(1);initial.update(prepared=True,nativeCycle=1,fieldAvailable=True,
            observationBoundary='main-task-queue-completion',fieldControl={'fieldPointer':100,'taskPointer':0})
        initial['actors']=[];evaluator.latest=deepcopy(initial)
        current=deepcopy(initial);current.update(frame=2,nativeCycle=2)
        follower=deepcopy(snapshot()['actors'][0]);follower.update(species=155,role='FOLLOWER',form=0,level=level,
            motionPhase='IDLE',reservationId=0)
        follower['handle'].update(slot=7,value=65543);current['actors']=[follower]
        current['selector']={'activeFollowerPartySlot':0,'followerReleaseState':0,'captureTargetMask':0,'queue':{'count':0,'request':0}}
        receipt={'lifecycle':'prepared-native-follower-lifecycle','preparedOnly':True,'snapshot':current,
            'requestedSubject':{'slot':0,'role':'FOLLOWER','species':155,'personality':123,'form':0,'level':level},
            'events':[],'setupBoundary':{'eventsDrained':True,'traceSequences':{},'frame':2,'nativeCycle':2,'endpointNativeCycle':2}}
        return evaluator,{'phase':'setup','action':action['id'],'command':'spawn','receipt':receipt,'snapshot':current}

    def test_behind_follower_is_a_separate_setup_owner_with_no_ram_credit(self):
        kind='ram-behind-entry-v1'
        for fault in (None,'species','personality','moving','stale','queue','wrong-action'):
            evaluator,row=self.fixture(kind);a=row['snapshot']['actors'][0]
            if fault=='species':a['species']=56
            elif fault=='personality':a['subjectIdentity']+=1
            elif fault=='moving':a['motionPhase']='MOVING'
            elif fault=='stale':a['handle']['fieldEpoch']+=1
            elif fault=='queue':row['snapshot']['selector']['queue']['count']=1
            elif fault=='wrong-action':row['action']='spawn-onix'
            result=evaluator.observe_prepared_command(row)
            with self.subTest(fault=fault):
                if fault:self.assertEqual(result['state'],'failed',result)
                else:
                    self.assertNotEqual(result['state'],'failed',result)
                    self.assertEqual(evaluator.subjects,{})
                    self.assertEqual(evaluator.sampled_frames,0)
                    self.assertEqual(evaluator.measurements[kind].prepared,[])
                    self.assertEqual(len(evaluator._prepared_attached),1)

    def test_current_auxiliary_follower_is_setup_only_not_onix_credit(self):
        evaluator,row=self.fixture();result=evaluator.observe_prepared_command(row)
        self.assertNotEqual(result['state'],'failed',result['failures'])
        self.assertEqual(evaluator.latest,row['snapshot']);self.assertEqual(evaluator.subjects,{})
        self.assertEqual(evaluator.sampled_frames,0)
        self.assertEqual(evaluator.measurements['ram-ledge-continuity-v1'].prepared,[])
        self.assertFalse(evaluator.measurements['ram-ledge-continuity-v1'].ready)
        self.assertEqual(len(evaluator._prepared_attached),1)
        self.assertEqual(evaluator.observe_prepared_command(row)['state'],'failed')

    def test_wrong_current_follower_and_unsettled_or_reordered_endpoint_reject(self):
        for fault in ('species','personality','slot','level','role','stale-context','unverified','duplicate','moving','reserved','release','queue','clock','lifecycle'):
            evaluator,row=self.fixture();r=row['receipt'];s=row['snapshot'];a=s['actors'][0]
            if fault in ('species','personality','slot','level'):r['requestedSubject'][fault]+=1
            elif fault=='role':r['requestedSubject']['role']='WILD'
            elif fault=='stale-context':a['handle']['fieldEpoch']+=1
            elif fault=='unverified':a['identityVerified']=False
            elif fault=='duplicate':s['actors'].append(deepcopy(a))
            elif fault=='moving':a['motionPhase']='MOVING'
            elif fault=='reserved':a['reservationId']=3
            elif fault=='release':s['selector']['followerReleaseState']=1
            elif fault=='queue':s['selector']['queue']['count']=1
            elif fault=='clock':r['setupBoundary']['frame']=1
            else:r['lifecycle']='spawn-prepared'
            with self.subTest(fault=fault):self.assertEqual(evaluator.observe_prepared_command(row)['state'],'failed')

    def test_onix_still_requires_exact_wild_prepared_receipt(self):
        evaluator,row=self.fixture();row['action']='spawn-onix'
        self.assertEqual(evaluator.observe_prepared_command(row)['state'],'failed')
        self.assertEqual(evaluator.measurements['ram-ledge-continuity-v1'].prepared,[])



class FollowerTransitionRangeTests(unittest.TestCase):
    """Copied data controls; native acceptance still needs the registered run."""
    root = Path(__file__).resolve().parents[2]

    def case(self):
        return json.loads((self.root / 'tests/overworld/test-recipes/world.transition.follower-rebind.json').read_text())

    @staticmethod
    def sample(frame, *, rebound=False, elapsed=None, terminal=False):
        current = snapshot(frame)
        epoch = 3 if rebound else 2
        map_id = 67 if rebound else 33
        current.update(nativeCycle=frame * 2, fieldAvailable=True,
                       observationBoundary='main-task-queue-completion',
                       context={'fieldEpoch': epoch, 'mapGeneration': epoch, 'mapId': map_id},
                       fieldControl={'fieldPointer': 36377180, 'taskPointer': 0})
        px, pz = ((574, 400) if rebound else (585, 406))
        current['player'] = dict(x=px, y=pz, x_prev=px, y_prev=pz,
            pos_x=(px << 16)+0x8000, pos_z=(pz << 16)+0x8000,
            unk88_y=0, flags=1, movement_cmd=0, facing=1)
        actor = current['actors'][0]
        actor.update(handle={'value': 131079, 'slot': 7, 'generation': 2,
                             'fieldEpoch': epoch, 'mapGeneration': epoch, 'encounterGeneration': 2},
                     role='FOLLOWER', species=155, behaviorFingerprint=4023481721,
                     motionKind='NONE', motionPhase='IDLE', motionElapsed=2, motionDuration=2,
                     reservationId=0, commitSequence=5 if rebound else 4,
                     logical={'x': 574 if terminal else 575 if rebound else 585,
                              'y': 401 if rebound else 407},
                     origin={'x': 575 if rebound else 585, 'y': 401 if rebound else 408},
                     target={'x': 574 if rebound else 585, 'y': 401 if rebound else 407},
                     sourceIdentity={'active': 1, 'species': 155, 'personality': 123, 'map_id': map_id},
                     engineIdentity={'active': True, 'in_manager': True, 'pointer': 36387156,
                                     'current_map_id': map_id, 'object_map_id': map_id})
        x, z = actor['logical'].values()
        actor['engineObject'] = dict(x_range=-1, y_range=-1, flags=1, facing=2,
            pos_x=(x << 16)+0x8000, pos_y=65536, pos_z=(z << 16)+0x8000, unk88_y=0)
        if elapsed is not None:
            actor.update(motionKind='WALK', motionPhase='MOVING', motionElapsed=elapsed,
                         reservationId=8, commitSequence=5,
                         logical={'x': 575, 'y': 401})
            actor['engineObject']['pos_x']=(575 << 16)+0x8000-elapsed*0x8000
        if terminal:
            actor['commitSequence']=6
        return current

    @staticmethod
    def native(sample, name, sequence, *, value_a=0, value_b=0, reason='OK'):
        handle = sample['actors'][0]['handle']
        return {'kind': 'native', 'frame': sample['frame'], 'data': {
            'traceStream': 1, 'sequence': sequence, 'actorHandle': handle['value'],
            'actor': {key: value for key, value in handle.items() if key != 'value'},
            'event': name, 'reason': reason, 'valueA': value_a, 'valueB': value_b}}

    def route_row(self):
        current = self.sample(2)
        return {'phase': 'setup', 'action': 'route-start', 'command': 'teleport',
                'snapshot': current, 'receipt': {'preparedOnly': True, 'snapshot': deepcopy(current),
                 'value': {'mapId': 33, 'x': 585, 'z': 406, 'facing': 1,
                           'constructor': {'boundary': 'native-task-factory-return'},
                           'environmentOwnership': 'transferred-to-native-Task_ScriptWarp',
                           'environmentBytes': 24},
                 'events': [], 'setupBoundary': {'eventsDrained': True, 'frame': 2,
                    'nativeCycle': 4, 'endpointNativeCycle': 4, 'traceSequences': {'1': 0}}}}

    def bound(self):
        from tools.overworld.devtools_follower_transition_measurement import FollowerTransitionMeasurement
        from tools.overworld.devtools_records import select_current_actor
        meter = FollowerTransitionMeasurement(validate_test(self.case()), max_frames=840)
        initial = self.sample(1); initial['context'].update(mapId=67, fieldEpoch=1, mapGeneration=1)
        meter.observe_record({'initialSnapshot': initial})
        meter.observe_record(self.route_row())
        for frame, command, action in ((3, 'party', 'prepare-cyndaquil'), (4, 'spawn', 'spawn-cyndaquil-follower')):
            current = self.sample(frame)
            meter.observe_record({'phase':'setup', 'action':action, 'command':command, 'snapshot':current,
                                  'receipt':{'preparedOnly':True, 'setupBoundary':{'traceSequences':{'1':0}}}})
        current = self.sample(4)
        meter.observe_record({'phase':'setup', 'action':'bind-cyndaquil-follower', 'command':'bind',
                              'snapshot':current, 'receipt':select_current_actor(current,current['actors'][0])})
        self.assertEqual(meter.failures, [])
        return meter

    def rows(self):
        rows=[]
        for frame, name in zip(range(5,9), ('MOTION_STARTED','LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED')):
            s=self.sample(frame)
            rows.append((s,[self.native(s,name,frame-4,value_a=1 if frame==5 else 0)]))
        s=self.sample(9,rebound=True)
        old=self.sample(9)
        rows.append((s,[self.native(old,'CONTEXT_CHANGED',5,value_a=2,value_b=3,reason='CONTEXT_LOST'),
                        self.native(s,'ACTOR_REBOUND',6,value_a=33,value_b=67)]))
        s=self.sample(10,rebound=True,elapsed=0)
        rows.append((s,[self.native(s,'MOTION_STARTED',7,value_a=1)]))
        rows.append((self.sample(11,rebound=True,elapsed=1),[]))
        s=self.sample(12,rebound=True,terminal=True)
        rows.append((s,[self.native(s,'LOGICAL_COMMIT',8),self.native(s,'MOTION_FINISHED',9),
                        self.native(s,'CONTROL_RETURNED',10)]))
        return rows

    def run_rows(self, rows):
        meter=self.bound()
        for current,events in rows:
            meter.observe(current,events)
            if meter.failures: break
        return meter.finish()

    def test_exact_route_setup_and_validator_reject_wrong_map_or_extra_warp(self):
        from tools.overworld.devtools_follower_transition_measurement import FollowerTransitionMeasurement
        self.assertEqual(self.case()['setup'][0]['args']['facing'], 1)
        for fault in ('map','facing','missing','extra'):
            case=self.case()
            if fault in ('map','facing'):case['setup'][0]['args'][fault] = 0 if fault == 'facing' else case['setup'][0]['args'][fault]+1
            elif fault=='missing':case['setup'].pop(0)
            else:case['setup'].insert(1,deepcopy(case['setup'][0]));case['setup'][1]['id']='extra-warp'
            with self.subTest(fault=fault),self.assertRaises(ValueError):validate_test(case)
        for fault in ('map','reserved','clock','drain','context','owner','repeat'):
            meter=FollowerTransitionMeasurement(validate_test(self.case()),max_frames=840)
            meter.observe_record({'initialSnapshot':self.sample(1)})
            row=self.route_row()
            if fault=='map':row['snapshot']['context']['mapId']=67
            elif fault=='reserved':row['snapshot']['player']['pos_x']-=1
            elif fault=='clock':row['receipt']['setupBoundary']['nativeCycle']=3
            elif fault=='drain':row['receipt']['setupBoundary']['eventsDrained']=False
            elif fault=='context':row['snapshot']['context']['fieldEpoch']=0
            elif fault=='owner':row['snapshot']['fieldControl']['fieldPointer']=0
            else:meter.observe_record(deepcopy(row))
            if fault!='repeat':row['receipt']['snapshot']=deepcopy(row['snapshot'])
            with self.subTest(fault=fault):self.assertTrue(meter.observe_record(row)['failures'])

    def test_shared_raw_admission_is_setup_only_and_no_motion_credit(self):
        evaluator=TestEvaluator(self.case())
        evaluator.install_measurements({'follower-transition-rebind-v1':{'contractVersion':1}})
        initial=self.sample(1);initial['actors']=[]
        evaluator.observe_record({'initialSnapshot':initial})
        row=self.route_row();row['receipt']['setupBoundary']['traceSequences']={}
        result=evaluator.observe_record(row)
        self.assertEqual(result['failures'],[])
        meter=evaluator.measurements['follower-transition-rebind-v1']
        self.assertEqual(evaluator.subjects,{})
        self.assertEqual(meter.lifecycle,[])
        self.assertFalse(meter.ready)
        self.assertEqual(evaluator.sampled_frames,0)
        self.assertEqual(evaluator.observe_record(self.route_row())['state'],'failed')

    def test_restored_current_ranges_and_fresh_walk_commit_required(self):
        from tools.overworld.devtools_follower_transition_proof import KIND, measurements
        result=self.run_rows(self.rows())
        self.assertTrue(result['passed'],result['failures'])
        self.assertTrue(result['restoredRanges'])
        self.assertEqual(result['postRebindMotion']['commitAfter'],6)
        replay={'passed':True,'failures':[],'measurements':{KIND:result}}
        record={'sessionId':'copied','sessionCleanup':{'sessionId':'copied','closed':True,'errors':[]}}
        self.assertEqual(len(measurements(replay,record)),6)
        for fault in ('range','post-motion'):
            copied=deepcopy(replay);m=copied['measurements'][KIND]
            if fault=='range':m['terminal']['actors'][0]['engineObject']['x_range']=255
            else:m['postRebindMotion']=None
            with self.subTest(fault=fault),self.assertRaisesRegex(ValueError,'restored signed ranges'):
                measurements(copied,record)

    def test_missing_context_control_keeps_the_context_failure(self):
        from tools.overworld.devtools_follower_transition_proof import (
            FollowerTransitionNegative, KIND, validate_negative_result,
        )
        fault = "wild-transition-missing-context"
        control = FollowerTransitionNegative(fault)
        meter = self.bound()
        for sample, events in self.rows():
            row = control.mutate({"phase": "observe", "samples": [sample],
                                  "events": events}, {"cyndaquil": meter.subject})
            meter.observe(row["samples"][0], row["events"])
        failed = meter.finish()
        self.assertTrue(control.applied)
        self.assertEqual([event["data"]["event"] for event in failed["transitionEvents"]],
                         ["ACTOR_REBOUND"])
        self.assertEqual(failed["failures"],
                         ["Wild transition did not complete context rebind and restore player control"])
        validate_negative_result({"passed": False, "failures": [],
                                  "measurements": {KIND: failed}}, fault)
        with self.assertRaisesRegex(ValueError, "unrelated reason"):
            validate_negative_result({"passed": False, "failures": ["other failure"]}, fault)
        rows = self.rows()[:5]
        self.assertEqual(self.run_rows(rows)["failures"],
                         ["Follower transition lacks signed -1/-1 and a fresh committed rebound Walk, or did not restore player control"])

    def test_wrong_range_stale_owner_missing_rebind_or_fresh_walk_rejected(self):
        for fault in ('range','stale-owner','missing-rebind','no-fresh-walk','missing-commit','wrong-start','wrong-frame'):
            rows=self.rows()
            if fault=='range':rows[4][0]['actors'][0]['engineObject']['y_range']=255
            elif fault=='stale-owner':rows[4][0]['actors'][0]['handle']['mapGeneration']=2
            elif fault=='missing-rebind':rows[4][1].pop()
            elif fault=='no-fresh-walk':rows=rows[:5]
            elif fault=='missing-commit':rows[-1][0]['actors'][0]['commitSequence']=5
            elif fault=='wrong-start':rows[5][1][0]['data']['valueA']=2
            else:rows[5][1][0]['frame']=9
            result=self.run_rows(rows)
            with self.subTest(fault=fault):self.assertFalse(result['passed']);self.assertTrue(result['failures'])


if __name__ == "__main__": unittest.main()
