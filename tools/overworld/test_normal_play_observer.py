"""Pure motion/chain/identity checks and shared callback controls; no game driver."""

import copy
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest import mock

from tools.overworld.normal_play_observer import (
    MotionRecorder, decode_lane, evaluate_chain_intervals, live_identity,
)
from tools.overworld.devtools_engine import Hooks
from tools.overworld.devtools_runtime import actor_identity_checks


REPO = Path(__file__).resolve().parents[2]


def actor_state():
    return {"active": True, "species": 165, "role": "WILD", "presentationAttached": True,
            "subjectIdentity": 55, "handle": {"value": 1, "slot": 0, "fieldEpoch": 2,
                                               "generation": 1, "mapGeneration": 1, "encounterGeneration": 1},
            "origin": {"x": 0, "y": 0}, "target": {"x": 2, "y": 2},
            "logical": {"x": 0, "y": 0}, "motionKind": "REPOSITION", "motionPhase": "MOVING",
            "commitSequence": 0, "motionDuration": 4, "motionElapsed": 1,
            "reservationId": 3, "behaviorFingerprint": 123}


def identity_records():
    actor = actor_state()
    source = {"active": 1, "species": 165, "object": 0x02010000, "object_id": 0xE0,
              "map_id": 33, "encounter_generation": 1, "personality": 55}
    engine = {"pointer": source["object"], "in_manager": True, "active": True,
              "object_manager": 1234, "current_manager": 1234,
              "object_id": 0xE0, "spawn_object_id": 0xE0,
              "object_map_id": 33, "spawn_map_id": 33, "current_map_id": 33,
              "encounter_generation": 1, "script_id": 2074}
    return actor, source, engine


def rendered(elapsed, duration=4):
    coordinate = 0x8000 + (2 * 0x10000 * elapsed // duration)
    return {"pos_x": coordinate, "pos_y": 0, "pos_z": coordinate,
            "facing": 1, "flags": 1, "unk88_y": 0}


def record_motion(*, freeze=False, terminal_short=False, reservation_release=False,
                  expected_pause=None, actual_pause=1):
    recorder = MotionRecorder()
    if expected_pause is not None:
        recorder.expected_pause_by_kind["REPOSITION"] = expected_pause
    actor = actor_state()
    for frame in range(1, 5):
        actor["motionElapsed"] = frame
        if reservation_release:
            actor["reservationId"] = 0
        engine = rendered(1 if freeze else frame)
        recorder.observe(frame, actor, engine)
    actor.update(motionPhase="SETTLING", commitSequence=1, motionElapsed=4)
    actor["logical"] = copy.deepcopy(actor["target"])
    for frame in range(5, 5 + actual_pause):
        recorder.observe(frame, actor, rendered(4))
    actor.update(motionPhase="IDLE", motionKind="NONE", reservationId=0)
    recorder.observe(5 + actual_pause, actor, rendered(3 if terminal_short else 4))
    return recorder


def lane():
    return {"ramAccelerationSteps": 8, "chainMovementVariance": 6, "chainPauseActionChance": 60,
            "chainRepositionJumpCount": 4, "chainRepositionSpeed": 4, "chainRepositionDistance": 2,
            "chainRepositionAllowCardinal": 0, "chainRepositionAllowDiagonal": 1}


def chain_fixture():
    boundaries = [{"frame": 10, "lane": lane(), "eligibleMoves": 8, "roll": 75, "selected": False},
                  {"frame": 30, "lane": lane(), "eligibleMoves": 22, "roll": 20, "selected": True}]
    motion = record_motion().completed[0]
    motions = [{**copy.deepcopy(motion), "startFrame": 31 + index * 6, "finishFrame": 36 + index * 6}
               for index in range(4)]
    return boundaries, motions


class LiveIdentityTests(unittest.TestCase):
    def test_native_active_flags_are_shared_and_bounded(self):
        from tools.overworld.spawn_identity import live_spawn_flags
        from tools.overworld.devtools_contract import source_paths
        import re
        header = (REPO / "include/overworld_wild_spawns_internal.h").read_text()
        for name, expected in (("OW_WILD_SPAWN_AGGRO_FLAG", 2),
                               ("OW_WILD_SPAWN_AGGRO_PENDING_FLAG", 4)):
            match = re.search(r"^#define " + name + r"\s+(0x[0-9A-Fa-f]+)\s*$", header, re.M)
            self.assertIsNotNone(match)
            self.assertEqual(int(match.group(1), 16), expected)
        actor, source, engine = identity_records()
        for flags in (*range(256), -1, 256, True, False, None, "3", 3.0):
            with self.subTest(flags=flags):
                expected = type(flags) is int and flags in (1, 3, 5, 7)
                self.assertEqual(live_spawn_flags(flags), expected)
                source["active"] = flags
                self.assertEqual(live_identity(actor, source, engine,
                    species=165, role="WILD", current_epoch=2), expected)
        self.assertIn("tools/overworld/spawn_identity.py", source_paths(REPO))

    def test_generated_descriptor_publishes_required_context_offset(self):
        from scripts import generate_overworld_actor_system_debug as debug
        symbols = {name: {"address": 1, "size": 2448}
                   for name in (*debug.MAIN_CALLBACKS, *debug.COMPAT_CALLBACKS, debug.STATE_SYMBOL)
                   if name is not None}
        layout = [0] * 28
        layout[18] = 12
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "debug.json")
            debug.write_descriptor(path, b"", symbols, layout, [], [0] * 8, {}, {}, {},
                                   debug.parse_context_offsets(REPO / "include/overworld_actor_system_internal.h"))
            descriptor = json.loads(Path(path).read_text())
        self.assertEqual(descriptor["state"]["offsets"].get("mapGeneration"), 46)

    def test_shared_observer_rejects_actor_from_previous_map_generation(self):
        actor, source, engine = identity_records()
        actor.update(authorityGeneration=1, engineAnchorGeneration=1, presentationGeneration=1)
        context = {"fieldEpoch": 2, "mapGeneration": 1, "mapId": 33}
        self.assertTrue(all(actor_identity_checks(actor, source, engine, context, 0).values()))
        actor["handle"]["mapGeneration"] = 2
        self.assertFalse(actor_identity_checks(actor, source, engine, context, 0)["mapGeneration"])

    def test_full_live_binding_is_required(self):
        actor, source, engine = identity_records()
        self.assertTrue(live_identity(actor, source, engine, species=165, role="WILD", current_epoch=2))
        for record, field, value in ((actor, "role", "MOUNTED"), (actor, "species", 155),
                                     (actor, "subjectIdentity", 99), (source, "personality", 99),
                                     (engine, "in_manager", False), (engine, "active", False),
                                     (engine, "script_id", 1), (engine, "current_map_id", 67),
                                     (source, "object_id", 0xE1)):
            with self.subTest(field=field, value=value):
                before = record[field]
                record[field] = value
                self.assertFalse(live_identity(actor, source, engine, species=165, role="WILD", current_epoch=2))
                record[field] = before

    def test_stale_epoch_and_wrong_slot_are_rejected(self):
        actor, source, engine = identity_records()
        self.assertFalse(live_identity(actor, source, engine, species=165, role="WILD", current_epoch=3))
        actor["handle"]["slot"] = 7
        self.assertFalse(live_identity(actor, source, engine, species=165, role="WILD", current_epoch=2))


class MotionRecorderTests(unittest.TestCase):
    def test_two_frame_successor_keeps_the_observed_prior_endpoint(self):
        for dx, dz in ((1,0),(-1,0),(0,1),(0,-1),(1,1)):
            for fault in (None, 'old-logical', 'new-logical', 'pose', 'gap', 'commit'):
                with self.subTest(direction=(dx,dz), fault=fault):
                    recorder = MotionRecorder()
                    actor = actor_state()
                    actor.update(motionKind='WALK')
                    for elapsed in range(1,5):
                        actor.update(motionElapsed=elapsed,
                            logical={'x':2,'y':2} if elapsed == 4 else {'x':0,'y':0},
                            motionPhase='COMMIT_PENDING' if elapsed == 4 else 'MOVING')
                        if elapsed == 4 and fault == 'old-logical': actor['logical']['x'] = 0
                        recorder.observe(elapsed, actor, rendered(elapsed))
                    actor.update(origin={'x':2,'y':2}, target={'x':2+dx,'y':2+dz},
                        logical={'x':2+dx,'y':2+dz}, motionElapsed=1, motionDuration=2,
                        motionPhase='MOVING', commitSequence=1)
                    engine = rendered(4)
                    engine['pos_x'] += dx*0x8000;engine['pos_z'] += dz*0x8000
                    if fault == 'new-logical': actor['logical'] = {'x':2,'y':2}
                    if fault == 'pose': engine['pos_x'] += 1
                    if fault == 'commit': actor['commitSequence'] = 0
                    recorder.observe(6 if fault == 'gap' else 5, actor, engine)
                    if fault:
                        self.assertTrue(recorder.failures)
                    else:
                        self.assertEqual(recorder.failures, [])
                        self.assertEqual(recorder.completed[0]['terminalLogical'], [2,2])
                        self.assertEqual(recorder.completed[0]['terminalRender'], [0x28000,0,0x28000])
                        self.assertEqual(recorder.current['samples'][0]['render'],
                                         [engine['pos_x'],0,engine['pos_z']])

    def test_observed_endpoint_precedes_elapsed_one_successor(self):
        for fault in (None, "elapsed-two", "missing-endpoint", "identity", "gap",
                      "pose", "origin", "logical", "commit"):
            with self.subTest(fault=fault):
                recorder = MotionRecorder(expected_pause_by_kind={"WALK": 0})
                actor = actor_state()
                actor.update(motionKind="WALK")
                for elapsed in range(1, 5):
                    if fault == "missing-endpoint" and elapsed == 4:
                        continue
                    actor.update(motionElapsed=elapsed,
                                 motionPhase="COMMIT_PENDING" if elapsed == 4 else "MOVING")
                    recorder.observe(elapsed, actor, rendered(elapsed))
                actor.update(origin={"x": 2, "y": 2}, target={"x": 3, "y": 2},
                             logical={"x": 2, "y": 2}, motionElapsed=1,
                             motionPhase="MOVING", commitSequence=1)
                engine = rendered(4)
                engine["pos_x"] += 0x4000
                if fault == "elapsed-two":
                    actor["motionElapsed"] = 2
                    engine["pos_x"] += 0x4000
                elif fault == "identity":
                    actor["handle"]["fieldEpoch"] += 1
                elif fault == "pose":
                    engine["pos_x"] += 1
                elif fault == "origin":
                    actor["origin"]["x"] += 1
                elif fault == "logical":
                    actor["logical"]["x"] += 1
                elif fault == "commit":
                    actor["commitSequence"] = 0
                recorder.observe(6 if fault == "gap" else 5, actor, engine)
                if fault is not None:
                    self.assertTrue(recorder.failures)
                else:
                    self.assertEqual(recorder.failures, [])
                    self.assertEqual(recorder.completed[0]["terminalRender"],
                                     [0x28000, 0, 0x28000])
                    self.assertEqual(recorder.completed[0]["travelEnd"]["frame"], 4)
                    self.assertEqual(recorder.current["samples"][0]["elapsed"], 1)

    def _record_successor_seam(self, *, fault=None, expected_pause=0, before_commit=0,
                               first_elapsed=0):
        recorder = MotionRecorder(expected_pause_by_kind={"WALK": expected_pause})
        actor = actor_state()
        actor.update(motionKind="WALK", motionDuration=8, motionElapsed=0,
                     commitSequence=before_commit)
        for elapsed in range(first_elapsed, 8):
            if fault == "missing-middle-frame" and elapsed == 4:
                continue
            if fault == "missing-final-frame" and elapsed == 7:
                continue
            actor["motionElapsed"] = elapsed
            recorder.observe(100 + elapsed, actor, rendered(elapsed, duration=8))
        target = copy.deepcopy(actor["target"])
        actor.update(origin=copy.deepcopy(target), target={"x": 3, "y": 2},
                     logical=copy.deepcopy(target), motionElapsed=0,
                     motionDuration=4, commitSequence=(before_commit + 1) & 0xFFFFFFFF)
        terminal = rendered(8, duration=8)
        frame = 108
        if fault == "early-successor":
            frame -= 1
        elif fault == "one-frame-gap":
            frame += 1
        elif fault == "far-render-pose":
            terminal["pos_x"] += 1
        elif fault == "wrong-logical-target":
            actor["logical"]["y"] += 1
        elif fault == "wrong-successor-origin":
            actor["origin"]["x"] += 1
        elif fault == "unchanged-counter":
            actor["commitSequence"] = before_commit
        elif fault == "wrong-full-handle":
            actor["handle"]["fieldEpoch"] += 1
        elif fault == "successor-already-moving":
            actor["motionElapsed"] = 1
        elif fault == "unfinished-hop-offset":
            terminal["unk88_y"] = 16
        recorder.observe(frame, actor, terminal)
        return recorder

    def test_contiguous_successor_origin_is_observed_terminal_pose(self):
        for before in (0, 0xFFFFFFFF):
            with self.subTest(commitBefore=before):
                recorder = self._record_successor_seam(before_commit=before)
                self.assertEqual(recorder.failures, [])
                self.assertEqual(len(recorder.completed), 1)
                previous = recorder.completed[0]
                self.assertEqual([sample["elapsed"] for sample in previous["samples"]], list(range(8)))
                self.assertEqual(previous["travelEnd"], {
                    "frame": 108, "elapsed": 8, "render": [0x28000, 0x28000],
                    "observedBy": "successor-origin", "successorElapsed": 0,
                })
                self.assertEqual(previous["pauseFrames"], 0)
                self.assertEqual(previous["commitAfter"], (before + 1) & 0xFFFFFFFF)
                self.assertEqual(recorder.current["startFrame"], 108)
                self.assertEqual(recorder.current["samples"][0]["elapsed"], 0)

    def test_successor_origin_does_not_fill_missing_time_identity_or_pose(self):
        for fault in ("early-successor", "missing-middle-frame", "missing-final-frame",
                      "one-frame-gap", "far-render-pose", "wrong-logical-target",
                      "wrong-successor-origin", "unchanged-counter", "wrong-full-handle",
                      "successor-already-moving", "unfinished-hop-offset"):
            with self.subTest(fault=fault):
                recorder = self._record_successor_seam(fault=fault)
                self.assertTrue(recorder.failures)
                self.assertIn("missing-terminal-commit" if fault == "unchanged-counter" else "incomplete-travel",
                              [item["reason"] for item in recorder.failures])

    def test_successor_terminal_pose_does_not_waive_authored_pause(self):
        recorder = self._record_successor_seam(expected_pause=1)
        self.assertIn("settle-pause-time", [item["reason"] for item in recorder.failures])

    def test_successor_seam_accepts_first_elapsed_one_but_not_two(self):
        recorder = self._record_successor_seam(first_elapsed=1)
        self.assertEqual(recorder.failures, [])
        self.assertEqual(recorder.completed[0]["startFrame"], 101)
        self.assertEqual(recorder.completed[0]["travelEnd"]["frame"], 108)
        self.assertEqual([sample["elapsed"] for sample in recorder.completed[0]["samples"]],
                         list(range(1, 8)))
        recorder = self._record_successor_seam(first_elapsed=2)
        self.assertIn("incomplete-travel", [item["reason"] for item in recorder.failures])
        for fault in ("missing-middle-frame", "wrong-successor-origin", "one-frame-gap"):
            with self.subTest(first_elapsed=1, fault=fault):
                recorder = self._record_successor_seam(first_elapsed=1, fault=fault)
                self.assertIn("incomplete-travel", [item["reason"] for item in recorder.failures])

    def test_shortened_normal_hop_cannot_be_completed_by_a_final_pose(self):
        recorder = MotionRecorder()
        actor = actor_state()
        actor["motionKind"] = "HOP"
        for frame in (1, 2):
            actor["motionElapsed"] = frame
            recorder.observe(frame, actor, rendered(frame))
        actor.update(motionPhase="IDLE", motionKind="NONE", motionElapsed=4, commitSequence=1)
        actor["logical"] = copy.deepcopy(actor["target"])
        recorder.observe(3, actor, rendered(4))
        self.assertIn("incomplete-travel", [item["reason"] for item in recorder.failures])

    def test_authored_pause_rejects_skipped_and_extended_settle(self):
        self.assertEqual(record_motion(expected_pause=3, actual_pause=3).failures, [])
        for actual in (0, 2, 4):
            with self.subTest(actual=actual):
                errors = record_motion(expected_pause=3, actual_pause=actual).failures
                self.assertIn("settle-pause-time", [item["reason"] for item in errors])
        self.assertEqual(record_motion(expected_pause=0, actual_pause=0).failures, [])

    def test_complete_live_progress_commits_once(self):
        recorder = record_motion()
        self.assertEqual(recorder.failures, [])
        self.assertEqual(len(recorder.completed), 1)
        self.assertEqual(recorder.completed[0]["finishFrame"], 6)

    def test_target_reservation_release_is_not_a_new_motion(self):
        self.assertEqual(record_motion(reservation_release=True).failures, [])

    def test_exact_duplicate_hook_is_ignored_not_a_stall(self):
        recorder = MotionRecorder()
        actor = actor_state()
        recorder.observe(1, actor, rendered(1))
        recorder.observe(1, actor, rendered(1))
        self.assertEqual(len(recorder.current["samples"]), 1)
        self.assertEqual(recorder.failures, [])

    def test_new_frame_with_no_render_progress_fails(self):
        self.assertIn("render-stall", [error["reason"] for error in record_motion(freeze=True).failures])

    def test_positive_but_short_travel_fails_at_terminal(self):
        self.assertIn("terminal-render-target", [error["reason"] for error in record_motion(terminal_short=True).failures])

    def test_repeated_elapsed_in_different_frame_is_not_deduplicated(self):
        recorder = MotionRecorder()
        actor = actor_state()
        recorder.observe(1, actor, rendered(1))
        recorder.observe(2, actor, rendered(1))
        self.assertIn("elapsed-gap", [error["reason"] for error in recorder.failures])

    def test_missing_terminal_commit_is_rejected(self):
        recorder = MotionRecorder()
        actor = actor_state()
        recorder.observe(1, actor, rendered(1))
        actor.update(motionPhase="IDLE", motionKind="NONE")
        recorder.observe(2, actor, rendered(4))
        self.assertIn("missing-terminal-commit", [error["reason"] for error in recorder.failures])


class ChainOracleTests(unittest.TestCase):
    def test_partial_chain_reset_does_not_join_seven_and_thirteen_moves(self):
        boundaries, motions = chain_fixture()
        boundaries = [{**boundaries[1], "eligibleMoves": 20}]
        call = bytearray(28)
        call[:4] = b"\x01\x00\x1c\x00"
        reset = {"frame": 15, "boundaryIndex": 0, "eligibleMoves": 7,
                 "reason": "explicit-policy-reset", "requestHex": call.hex(),
                 "responseHex": call.hex(), "returned": True,
                 "laneTransition": {"fromLaneState": 0, "toLaneState": 2,
                     "beforeFrame": 10, "frame": 20, "eligibleMoves": 7, "boundaryIndex": 0}}
        result = evaluate_chain_intervals(boundaries, motions, resets=[reset])
        self.assertTrue(result["passed"], result)
        self.assertEqual([item["count"] for item in result["intervals"]], [13])
        self.assertEqual(result["interruptedIntervals"][0]["count"], 7)
        self.assertEqual(result["interruptedIntervals"][0]["reset"], reset)
        self.assertFalse(evaluate_chain_intervals(boundaries, motions)["passed"])
        unexplained = {key: value for key, value in reset.items() if key != "laneTransition"}
        self.assertIn("unexplained-chain-reset", [item["reason"] for item in
            evaluate_chain_intervals(boundaries, motions, resets=[unexplained])["errors"]])
        # A late reset is not permission to hide an already overlong chain.
        reset["eligibleMoves"], boundaries[0]["eligibleMoves"] = 20, 33
        reset["laneTransition"]["eligibleMoves"] = 20
        self.assertIn("chain-reset-after-range", [item["reason"] for item in
            evaluate_chain_intervals(boundaries, motions, resets=[reset])["errors"]])

    def test_reset_receipt_requires_the_observed_public_reset_result(self):
        boundaries, motions = chain_fixture()
        call = bytearray(28)
        call[:4] = b"\x01\x00\x1c\x00"
        reset = {"frame": 5, "boundaryIndex": 0, "eligibleMoves": 0,
                 "reason": "explicit-policy-reset", "requestHex": call.hex(),
                 "responseHex": call.hex(), "returned": True}
        for change in ({"returned": False}, {"responseHex": "00"},
                       {"reason": "lane-changed"}, {"boundaryIndex": 3},
                       {"eligibleMoves": 30}):
            with self.subTest(change=change):
                self.assertFalse(evaluate_chain_intervals(
                    boundaries, motions, resets=[{**reset, **change}])["passed"])

    def test_natural_chance_skip_starts_a_new_independent_interval(self):
        boundaries, motions = chain_fixture()
        result = evaluate_chain_intervals(boundaries, motions)
        self.assertTrue(result["passed"], result)
        self.assertEqual([item["count"] for item in result["intervals"]], [8, 14])
        self.assertEqual(len(result["actions"]), 1)

    def test_three_moves_cannot_satisfy_eight_to_fourteen(self):
        boundaries, motions = chain_fixture()
        boundaries[0]["eligibleMoves"] = 3
        self.assertFalse(evaluate_chain_intervals(boundaries, motions)["passed"])

    def test_missing_reposition_motion_cannot_pass(self):
        boundaries, motions = chain_fixture()
        self.assertFalse(evaluate_chain_intervals(boundaries, motions[:-1])["passed"])

    def test_counting_only_endpoints_cannot_hide_wrong_time_or_facing(self):
        for mutation in ("duration", "samples", "facing", "distance"):
            boundaries, motions = chain_fixture()
            if mutation == "duration":
                motions[0]["duration"] = 2
            elif mutation == "samples":
                motions[0]["samples"].pop(1)
            elif mutation == "facing":
                motions[0]["samples"][1]["facing"] = 2
            else:
                motions[0]["target"] = [1, 1]
            with self.subTest(mutation=mutation):
                self.assertFalse(evaluate_chain_intervals(boundaries, motions)["passed"])

    def test_wrong_chance_decision_is_rejected(self):
        boundaries, motions = chain_fixture()
        boundaries[0]["selected"] = True
        self.assertIn("chance-selection", [item["reason"] for item in evaluate_chain_intervals(boundaries, motions)["errors"]])

    def test_schema_driven_lane_does_not_need_private_policy_state(self):
        schema = json.loads((REPO / "tools/overworld/behavior_schema.json").read_text())
        values = decode_lane(bytes(schema["compactSize"]), schema)
        self.assertEqual(values["chainRepositionSpeed"], 0)
        with self.assertRaises(ValueError):
            decode_lane(bytes(3), schema)


class SharedHookTests(unittest.TestCase):
    def test_callback_errors_are_retained_instead_of_silent_pass(self):
        registered = {}
        memory = SimpleNamespace(register_exec=lambda address, callback: registered.__setitem__(address, callback))
        hooks = Hooks(None, SimpleNamespace(memory=memory))
        hooks.add(0x02000001, lambda: (_ for _ in ()).throw(ValueError("bad ABI")))
        registered[0x02000000](0, 0)
        self.assertIn("bad ABI", hooks.error)
        hooks.close()
        self.assertIsNone(registered[0x02000000])

    def test_first_callback_error_stops_later_observers_without_replacing_cause(self):
        registered, later = {}, []
        memory = SimpleNamespace(register_exec=lambda address, callback: registered.__setitem__(address, callback))
        hooks = Hooks(None, SimpleNamespace(memory=memory))
        hooks.add(0x02000001, lambda: (_ for _ in ()).throw(ValueError("original cause")))
        hooks.add(0x02000003, lambda: later.append(True))
        registered[0x02000000](0, 0)
        first_error = hooks.error
        registered[0x02000002](0, 0)
        registered[0x02000000](0, 0)
        self.assertEqual(later, [])
        self.assertEqual(hooks.error, first_error)
        self.assertIn("0x02000000", hooks.error)
        self.assertIn("original cause", hooks.error)


if __name__ == "__main__":
    unittest.main()
