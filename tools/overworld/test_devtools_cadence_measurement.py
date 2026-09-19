"""Shared-shape synthetic replay controls, not live gameplay acceptance."""
from copy import deepcopy
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tools.overworld.devtools_cadence_measurement import UnmountedCadenceMeasurement


def actual_terminal_abi():
    """Compile the production trace body; do not reuse the meter's constants."""
    root = Path(__file__).resolve().parents[2]
    header = (root / "include/overworld_actor_system.h").read_text()
    kinds = {name: int(value) for name, value in re.findall(
        r"OVERWORLD_ACTOR_MOTION_(WALK|REPOSITION)\s*=\s*(\d+)", header)}
    if set(kinds) != {"WALK", "REPOSITION"}:
        raise AssertionError("actual motion enum seam changed")
    source = (root / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c").read_text()
    match = re.search(r"static void ActorSystem_WriteTerminalTrace\([^{}]*\)\s*\{[^{}]*\}", source)
    if not match:
        raise AssertionError("actual terminal trace body seam changed")
    fixture = """#include <stdio.h>
typedef unsigned int u32;
typedef unsigned short u16;
typedef struct { u32 handle, inputOwnership, commitSequence; } OverworldActorStateSnapshot;
enum { OVERWORLD_ACTOR_EVENT_CONTROL_RETURNED = 400 };
static u32 controlA, controlB;
static void ActorSystem_WriteTrace(void *handle, u16 event, u16 reason, u32 a, u32 b)
{ (void)handle; (void)reason; if (event == OVERWORLD_ACTOR_EVENT_CONTROL_RETURNED) { controlA = a; controlB = b; } }
""" + match[0] + """
int main(void) { OverworldActorStateSnapshot actor = { 7, 0, 1 };
    ActorSystem_WriteTerminalTrace(&actor, 21, 0, 1, 1);
    printf("%u %u\\n", controlA, controlB); return 0; }
"""
    compiler = shutil.which("cc")
    if compiler is None:
        raise AssertionError("host C compiler is required for the actual trace body")
    with tempfile.TemporaryDirectory() as directory:
        source_path, executable = Path(directory) / "terminal.c", Path(directory) / "terminal"
        source_path.write_text(fixture)
        subprocess.run([compiler, "-std=c99", "-Wall", "-Wextra", "-Werror", str(source_path), "-o", str(executable)],
                       check=True, capture_output=True, text=True, timeout=30)
        actual = subprocess.run([str(executable)], check=True, capture_output=True, text=True, timeout=5)
    return kinds, tuple(int(value) for value in actual.stdout.split())


def player(x=0, z=0):
    return {"flags": 1, "x": x, "y": z, "x_prev": x, "y_prev": z,
            "pos_x": x * 65536 + 32768, "pos_y": 0, "pos_z": z * 65536 + 32768,
            "unk88_y": 0, "movement_cmd": 3, "movement_step": 0, "facing": 3}


def follower_object(x=0, z=0):
    return {**player(x, z), "flags": 0x40001}


class Route:
    """Authored32-frame tiles; no production movement formula supplies poses."""
    def __init__(self, *, fainted=False):
        self.frame = self.seq = self.trace_seq = self.steps = 0
        self.records = []
        self.p = player()
        self.mon = {"slot": 1, "species": 155, "personality": 123456, "form": 0, "level": 7,
                    "hp": 0 if fainted else 30, "maxHp": 30, "status": 0, "isEgg": False, "identityVerified": True}
        self.context = {"mapId": 33, "fieldEpoch": 2, "mapGeneration": 3}
        self.actor = {"active": True, "species": 155, "form": 0, "level": 7, "role": "FOLLOWER",
            "subjectIdentity": 123456, "behaviorFingerprint": 7,
            "handle": {"value": 65543, "slot": 7, "generation": 1, "fieldEpoch": 2,
                       "mapGeneration": 3, "encounterGeneration": 1},
            "presentationAttached": True, "identityVerified": True,
            "authorityGeneration": 1, "engineAnchorGeneration": 1, "presentationGeneration": 1,
            "origin": {"x": 0, "y": 1}, "target": {"x": 0, "y": 1}, "logical": {"x": 0, "y": 1},
            "motionKind": "NONE", "motionPhase": "IDLE", "motionElapsed": 0, "motionDuration": 0,
            "reservationId": 0, "inputOwnership": 0, "commitSequence": 0,
            "engineObject": follower_object(0, 1),
            "sourceIdentity": {"object": 0x02010000, "active": 1, "species": 155, "form": 0, "level": 7,
                "personality": 123456, "object_id": 231, "map_id": 33, "encounter_generation": 1},
            "engineIdentity": {"pointer": 0x02010000, "in_manager": True, "active": True,
                "object_manager": 0x02020000, "current_manager": 0x02020000, "object_id": 231,
                "spawn_object_id": 231, "object_map_id": 33, "spawn_map_id": 33, "current_map_id": 33,
                "encounter_generation": 1, "script_id": 2074}}
        self.selector = {"newKeys": 0, "heldKeys": 0, "state": 0, "highlight": 1, "activeFollowerPartySlot": 1}
        self.getters = []
        budget = {"maxSeconds": 300, "maxFrames": 600, "noProgressFrames": 240}
        def action(name, keys):
            return {"id": name, "op": "step", "args": {"frames": 512, "keys": keys}, "budget": budget}
        self.test = {"mode": "normal", "fixture": {"save": "test.sav"},
            "subjects": [{"id": "cyndaquil", "species": 155, "role": "FOLLOWER"}],
            "setup": [action("nurse", ["A"]), action("exit", []), action("open", ["Y"]), action("choose", ["Y"])],
            "actions": [{"id": "bind", "op": "bind", "args": {"subject": "cyndaquil"}, "budget": budget},
                        *[action("route-" + str(n), ["RIGHT"]) for n in range(12)], action("idle", [])]}
        self.records.append({"phase": "setup", "initialSnapshot": self.snapshot()})

    def snapshot(self):
        actor = deepcopy(self.actor)
        actor.setdefault("crashPresentation", {
            "known": True, "reason": "observed", "frame": self.frame,
            "nativeCycle": self.frame * 2, "boundary": "main-task-queue-completion",
            "timer": 0, "baseX": 0, "baseZ": 0,
            "objectPointer": actor["engineIdentity"]["pointer"], "handle": deepcopy(actor["handle"]),
        })
        return {"frame": self.frame, "nativeCycle": self.frame * 2, "actorFrame": self.frame,
            "observationBoundary": "main-task-queue-completion", "prepared": False,
            "fieldAvailable": True,
            "romSha256": "a" * 64, "sourceSaveSha256": "b" * 64,
            "context": deepcopy(self.context), "player": deepcopy(self.p), "actors": [actor],
            "fieldControl": {"fieldPointer": 0x02200000, "taskPointer": 0, "actorTransitionPhase": 0},
            "selector": deepcopy(self.selector), "party": [{"slot": 0}, deepcopy(self.mon)],
            "partyObservation": {"frame": self.frame, "boundary": "main-task-queue-completion",
                                 "nativeGetterChecks": deepcopy(self.getters)},
            "nativeObservation": {"installedBeforeBoot": True, "coverageComplete": True,
                "sequence": self.seq, "eventsDropped": 0, "profilesEvicted": 0, "error": None,
                "pendingUnframedEvents": 0, "pendingPlayerSteps": 0,
                "playerStepCount": self.steps, "playerStepFrame": self.frame}}

    def trace(self, name, a, b, *, handle=None):
        self.trace_seq += 1
        handle = handle or self.actor["handle"]
        return {"frame": self.frame + 1, "kind": "native", "data": {
            "traceStream": 1, "sequence": self.trace_seq, "actorHandle": handle["value"],
            "actor": {key: value for key, value in handle.items() if key != "value"},
            "event": name, "valueA": a, "valueB": b}}

    def admission(self, origin, target):
        self.seq += 1; self.steps += 1
        after = player(*origin); after.update(x=target[0], y=target[1])
        return {"frame": self.frame + 1, "kind": "native-observation", "data": {
            "observation": "player-step-admitted", "sequence": self.seq, "setupMode": "normal",
            "stepIndex": self.steps, "objectPointer": 0x02030000, "mapId": self.context["mapId"],
            "origin": origin, "target": target, "objectBefore": player(*origin), "objectAfter": after}}

    def append(self, action, *, phase="observe", events=()):
        previous = self.frame
        self.frame += 1
        if phase == "observe":
            keys = next((a["args"].get("keys", []) for a in self.test["actions"] if a["id"] == action), [])
            self.selector["heldKeys"] = sum({"UP":64,"DOWN":128,"LEFT":32,"RIGHT":16}.get(k, 0) for k in keys)
        self.records.append({"phase": phase, "action": action, "samples": [self.snapshot()],
            "events": deepcopy(list(events)), "nativeCycles": 2, "completedGameFrames": 1,
            "requestedGameFrames": 1, "observedFieldFrames": 1,
            "cycleIntervals": [{"cpuNs": 100000, "wallNs": 150000, "completedGameFrame": previous},
                               {"cpuNs": 100000, "wallNs": 150000, "completedGameFrame": self.frame}]})

    def setup_bind(self, *, heal=False):
        if heal:
            self.context["mapId"] = 69; self.p = player(8, 13)
            self.selector["newKeys"] = 1
            self.append("nurse", phase="setup")
            self.mon["hp"] = 30
            self.getters = [{"slot": 1, "field": "hp", "native": 30, "decoded": 30, "passed": True,
                "boundary": "natural-GetMonData-return", "personality": 123456, "species": 155,
                "frame": self.frame + 1, "decodedAtFrame": self.frame + 1}]
            self.append("nurse", phase="setup")
            self.context["mapId"] = 33; self.p = player(); self.selector["newKeys"] = 0
            self.append("exit", phase="setup")
        self.selector.update(newKeys=2048, state=2)
        self.append("open", phase="setup")
        self.selector.update(newKeys=2048, state=0)
        if not self.getters:
            self.getters = [{"slot": 1, "field": "hp", "native": self.mon["hp"], "decoded": self.mon["hp"],
                "passed": True, "boundary": "natural-GetMonData-return", "personality": 123456, "species": 155,
                "frame": self.frame + 1, "decodedAtFrame": self.frame + 1}]
        self.append("choose", phase="setup")
        self.selector["newKeys"] = 0
        self.records.append({"phase": "observe", "action": "bind", "command": "bind",
            "receipt": deepcopy(self.actor), "snapshot": self.snapshot()})

    def move(self, tile_index):
        origin, target = [tile_index - 1, 0], [tile_index, 0]
        follow = tile_index % 8 == 1
        follower_x = self.actor["logical"]["x"]
        for elapsed in range(1, 33):
            events = [self.admission(origin, target)] if elapsed == 1 else []
            self.p.update(x=target[0], y=0, x_prev=origin[0], y_prev=0, flags=0x11,
                          movement_cmd=15, pos_x=origin[0] * 65536 + 32768 + 2048 * elapsed)
            if follow and elapsed <= 8:
                self.actor.update(motionKind="WALK", motionPhase="MOVING", motionElapsed=elapsed - 1,
                    motionDuration=8, reservationId=1, origin={"x": follower_x, "y": 1},
                    target={"x": follower_x + 1, "y": 1})
                self.actor["engineObject"]["pos_x"] = follower_x * 65536 + 32768 + 8192 * (elapsed - 1)
                if elapsed == 1: events.append(self.trace("MOTION_STARTED", 1, 8))
            elif follow and elapsed == 9:
                self.actor.update(motionKind="NONE", motionPhase="IDLE", motionElapsed=8, reservationId=0,
                    commitSequence=self.actor["commitSequence"] + 1, logical={"x": follower_x + 1, "y": 1})
                self.actor["engineObject"] = follower_object(follower_x + 1, 1)
                events += [self.trace(name, 0 if name == "CONTROL_RETURNED" else self.actor["commitSequence"],
                                     self.actor["commitSequence"] if name == "CONTROL_RETURNED" else 1)
                           for name in ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")]
            if elapsed == 32:
                self.p.update(flags=0x31)
                if tile_index == 64:
                    old = deepcopy(self.actor["handle"])
                    self.context.update(mapId=67, fieldEpoch=3, mapGeneration=4)
                    self.actor["handle"].update(fieldEpoch=3, mapGeneration=4)
                    self.actor["sourceIdentity"]["map_id"] = 67
                    for key in ("object_map_id", "spawn_map_id", "current_map_id"):
                        self.actor["engineIdentity"][key] = 67
                    events += [self.trace("CONTEXT_CHANGED", 2, 3, handle=old), self.trace("ACTOR_REBOUND", 33, 67)]
            self.append("route-" + str((tile_index - 1) // 16), events=events)


def replay(route, *, finish=True, diagnostic_continue_host_hitches=False):
    evaluator = UnmountedCadenceMeasurement(route.test, max_frames=32000,
        diagnostic_continue_host_hitches=diagnostic_continue_host_hitches)
    for record in route.records:
        result = evaluator.observe_record(record)
        if result["failures"]: break
    return evaluator, evaluator.finish() if finish else evaluator.result()


class CadenceMetadataAvailabilityTests(unittest.TestCase):
    def test_base_form_cache_failure_is_an_immediate_failure(self):
        for returned in (0, 1):
            meter = UnmountedCadenceMeasurement(Route().test, max_frames=600)
            meter._events([{"frame": 1, "kind": "native-observation", "data": {
                "sequence": 1, "setupMode": "normal", "observation": "spawn-metadata",
                "returnValue": returned, "arguments": [163, 0, 0x027E3300, 0]}}], 1)
            self.assertEqual(bool(meter.failures), returned == 0)
            if returned == 0:
                self.assertEqual(meter.failures[0]["code"], "spawn-metadata-unavailable")
                self.assertEqual(meter.failures[0]["frame"], 1)


class CadenceStockTurnTests(unittest.TestCase):
    def fixture(self):
        route = Route(); route.p = player(585, 406); route.p.update(facing=1, movement_cmd=1, movement_step=1, flags=0x31)
        route.frame = 1115
        meter = UnmountedCadenceMeasurement(route.test, max_frames=32000)
        meter.latest = route.snapshot()
        rows = []
        # Retained manual 1116..1123: old poll, three turn updates, four
        # translated updates. Coordinates and command phases are independent
        # inputs, not output from the production movement classifier.
        for frame, held, command, step, flags in (
                (1116,0,1,1,0x31), (1117,64,40,1,0x11),
                (1118,64,40,1,0x11), (1119,64,40,2,0x31),
                (1120,64,88,1,0x11), (1121,64,88,1,0x11),
                (1122,64,88,1,0x11), (1123,64,88,2,0x31)):
            route.frame = frame; route.selector["heldKeys"] = held
            route.p.update(movement_cmd=command, movement_step=step, flags=flags, facing=1 if frame==1116 else 0)
            admissions = []
            if frame >= 1120:
                before = player(585,406)
                route.p.update(y=405, pos_z=406*65536+32768-(frame-1119)*16384)
                if frame == 1120:
                    after = deepcopy(before); after.update(y=405)
                    admissions = [{"objectPointer":0x02030000,"origin":[585,406],"target":[585,405],
                        "objectBefore":before,"objectAfter":after,"mapId":33}]
            rows.append((route.snapshot(), admissions))
        return meter, rows

    def run_rows(self, meter, rows):
        for snapshot, admissions in rows:
            meter._player(snapshot, ["UP"], admissions)
            meter.latest = deepcopy(snapshot)
            if meter.failures: break

    def test_retained_poll_turn_then_translation_has_separate_phase(self):
        meter, rows = self.fixture(); self.run_rows(meter, rows)
        self.assertEqual(meter.failures, [])
        self.assertEqual(meter.player_motions, 1)
        self.assertEqual(meter.active_frames, 4)
        self.assertEqual([s["phase"] for s in meter.motion_tail[-1]["inputPhase"]],
                         ["awaiting-input", "stock-turn", "stock-turn", "stock-turn"])

    def test_malformed_or_unconsumed_turn_is_rejected(self):
        for fault in ("missing-input", "missing-field", "pose", "facing", "command", "early-terminal", "prolonged"):
            with self.subTest(fault=fault):
                meter, rows = self.fixture()
                row = rows[1][0]
                if fault=="missing-input": row["selector"]["heldKeys"] = 0
                elif fault=="missing-field": del row["selector"]["heldKeys"]
                elif fault=="pose": row["player"]["pos_z"] += 1
                elif fault=="facing": row["player"]["facing"] = 1
                elif fault=="command": row["player"]["movement_cmd"] = 41
                elif fault=="early-terminal": row["player"].update(movement_step=2,flags=0x31)
                else: rows[3][0]["player"].update(movement_step=1,flags=0x11)
                with self.assertRaises(ValueError): self.run_rows(meter, rows)

    def test_finished_turn_does_not_relax_translation_admission_deadline(self):
        meter, rows = self.fixture(); self.run_rows(meter, rows[:4])
        for frame in (1120,1121,1122):
            row = deepcopy(rows[3][0]); row["frame"] = frame
            meter._player(row, ["UP"], [])
            meter.latest = row
        self.assertEqual(meter.failures[0]["code"], "player-input-not-admitted")

    def test_stationary_input_phases_require_current_active_player(self):
        for index in (0, 1, 3):
            for fault in ("mapId", "fieldEpoch", "mapGeneration", "inactive", "disabled"):
                with self.subTest(index=index, fault=fault):
                    meter, rows = self.fixture()
                    row = rows[index][0]
                    if fault in ("mapId", "fieldEpoch", "mapGeneration"):
                        row["context"][fault] += 1
                    elif fault == "inactive":
                        row["player"]["flags"] &= ~1
                    else:
                        row["player"]["flags"] |= 2
                    with self.assertRaises(ValueError):
                        self.run_rows(meter, rows)


class CadenceFollowerPassThroughTests(unittest.TestCase):
    def test_bad_terminal_keeps_exact_frame_and_both_pose_failures(self):
        route, _ = CadenceCanceledHandoffTests().fixture()
        terminal = route.records[-1]["samples"][0]
        actor = terminal["actors"][0]
        actor["engineObject"]["pos_x"] += 256
        actor["engineObject"]["pos_z"] -= 256
        _, result = replay(route, finish=False)
        failure = result["failures"][0]
        self.assertEqual(failure["frame"], terminal["frame"])
        self.assertEqual(failure["detail"]["reason"], "incomplete-travel")
        self.assertEqual(failure["detail"]["additionalFailures"][0]["reason"], "terminal-render-target")

    def test_flag_matches_product_role_contract(self):
        root = Path(__file__).resolve().parents[2]
        source = (root / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
        self.assertIn("BOOL passThrough = slot == OW_WILD_FOLLOWER_SLOT", source)
        self.assertIn("object->flags |= MAPOBJECTFLAG_UNK18;", source)
        header = (root / "include/map_events_internal.h").read_text()
        self.assertRegex(header, r"MAPOBJECTFLAG_UNK18\s*=\s*\(1\s*<<\s*18\)")

    def test_verified_follower_loss_reports_exact_completed_frame(self):
        for phase in ("IDLE", "MOVING", "CANCELED"):
            with self.subTest(phase=phase):
                route = Route(); route.setup_bind()
                route.actor["motionPhase"] = phase
                route.actor["engineObject"]["flags"] &= ~0x40000
                route.append("route-0")
                _, result = replay(route, finish=False)
                failure = result["failures"][0]
                self.assertEqual(failure["code"], "follower-pass-through-lost")
                self.assertEqual(failure["frame"], route.frame)
                self.assertEqual(failure["detail"], {"frame": route.frame,
                    "handle": route.actor["handle"], "flags": 1})

    def test_role_flag_is_not_added_to_player(self):
        route = Route(); route.setup_bind(); route.append("route-0")
        self.assertEqual(route.p["flags"], 1)
        self.assertEqual(replay(route, finish=False)[1]["failures"], [])

    def test_retained_transition_flag_loss_projection(self):
        # Exact flags, clocks and handle from recording-cdd29c9f50f8 frames
        # 1214/1215. Other actor fields use the shared verified-identity fixture.
        route = Route(); route.setup_bind()
        meter, _ = replay(route, finish=False)
        route.frame = 1214
        route.actor["engineObject"]["flags"] = 0x4E405
        route.actor["handle"].update(value=131079, generation=2,
            fieldEpoch=2, mapGeneration=2, encounterGeneration=2)
        route.context.update(mapId=33, fieldEpoch=2, mapGeneration=2)
        route.actor["sourceIdentity"]["encounter_generation"] = 2
        route.actor["engineIdentity"]["encounter_generation"] = 2
        meter.latest = route.snapshot()
        meter.actor = deepcopy(route.actor)
        meter.subject = deepcopy(route.actor)
        self.assertTrue(route.actor["engineObject"]["flags"] & 0x40000)
        route.frame = 1215
        route.context.update(mapId=67, fieldEpoch=3, mapGeneration=3)
        route.actor["handle"].update(fieldEpoch=3, mapGeneration=3)
        route.actor["sourceIdentity"]["map_id"] = 67
        for key in ("object_map_id", "spawn_map_id", "current_map_id"):
            route.actor["engineIdentity"][key] = 67
        route.actor.update(motionPhase="CANCELED")
        route.actor["engineObject"]["flags"] = 0xC421
        meter._follower(route.snapshot())
        self.assertEqual(meter.failures, [{"code": "follower-pass-through-lost", "frame": 1215,
            "detail": {"frame": 1215, "handle": route.actor["handle"], "flags": 0xC421}}])


class CadenceCanceledHandoffTests(unittest.TestCase):
    def test_already_qualified_canceled_handoff_needs_new_successful_motion(self):
        route, boundary = self.fixture()
        prefix = deepcopy(route); prefix.records = prefix.records[:boundary + 1]
        meter, _ = replay(prefix, finish=False)
        # Isolate the final readiness condition: all route floors were already met.
        meter.active_frames = 5000
        meter.tiles = {(x, 0) for x in range(256)}
        meter.cells = {(x, 0) for x in range(16)}
        meter.maps = {33, 34, 67}
        meter.follower_motions = 100
        meter.held_tiles = meter.held_cells = meter.held_maps = True
        self.assertFalse(meter.result()["ready"])
        for record in route.records[boundary + 1:]:
            meter.observe_record(record)
        self.assertEqual(meter.result()["failures"], [])
        self.assertTrue(meter.result()["ready"])
        recovery = meter.result()["handoffs"][0]["recoveryTerminal"]
        self.assertEqual(recovery["handle"], route.actor["handle"])

    def fixture(self, *, cancel_before_travel=False, cancel_elapsed=0):
        route = Route(); route.setup_bind()
        a = route.actor
        canceled_x = 0 if cancel_before_travel else 1
        for elapsed in range(cancel_elapsed + 1 if cancel_before_travel else 7):
            a.update(motionKind="WALK", motionPhase="MOVING", motionElapsed=elapsed,
                     motionDuration=8, reservationId=448, origin={"x": 0, "y": 1},
                     target={"x": 1, "y": 1}, logical={"x": canceled_x, "y": 1})
            a["engineObject"]["pos_x"] = 32768 + elapsed * 8192
            events = [route.trace("MOTION_STARTED", 1, 8)] if elapsed == 0 else []
            route.append("idle", events=events)
        old = deepcopy(a["handle"])
        events = [route.trace("MOTION_CANCELED", 1, 0), route.trace("CONTROL_RETURNED", 0, 0),
                  route.trace("CONTEXT_CHANGED", 2, 3)]
        for event in events:
            event["data"].update(reason="CONTEXT_LOST", reasonId=16)
        a["handle"].update(fieldEpoch=3, mapGeneration=4)
        route.context.update(mapId=67, fieldEpoch=3, mapGeneration=4)
        a["sourceIdentity"]["map_id"] = 67
        for k in ("object_map_id", "spawn_map_id", "current_map_id"):
            a["engineIdentity"][k] = 67
        a.update(motionPhase="CANCELED", reservationId=0, lastCancelReason=16)
        a["engineObject"] = follower_object(canceled_x, 1)
        events.append(route.trace("ACTOR_REBOUND", 33, 67))
        events[-1]["data"].update(reason="OK", reasonId=0)
        for event in events:
            event["data"]["actorFrame"] = route.frame + 1
        route.append("idle", events=events)
        boundary = len(route.records) - 1
        a["motionKind"] = "NONE"
        route.append("idle")
        route.append("idle")
        # A distinct subsequent move must still pass ordinary full travel.
        for elapsed in range(9):
            a.update(motionKind="WALK" if elapsed < 8 else "NONE",
                     motionPhase="MOVING" if elapsed < 8 else "IDLE",
                     motionElapsed=elapsed, motionDuration=8,
                     reservationId=1 if elapsed < 8 else 0,
                     origin={"x": canceled_x, "y": 1}, target={"x": canceled_x + 1, "y": 1})
            a["engineObject"]["pos_x"] = 32768 + canceled_x * 65536 + elapsed * 8192
            events = [route.trace("MOTION_STARTED", 1, 8)] if elapsed == 0 else []
            if elapsed == 8:
                a.update(commitSequence=1, logical={"x": canceled_x + 1, "y": 1})
                events = [route.trace("LOGICAL_COMMIT", 1, 1), route.trace("MOTION_FINISHED", 1, 1),
                          route.trace("CONTROL_RETURNED", 0, 1)]
            route.append("idle", events=events)
        return route, boundary

    def test_cancel_before_travel_preserves_origin_without_commit_credit(self):
        route, boundary = self.fixture(cancel_before_travel=True)
        prefix = deepcopy(route); prefix.records = prefix.records[:boundary + 1]
        _, result = replay(prefix, finish=False)
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["followerMotions"], 0)
        terminal = result["handoffs"][0]["canceledMotion"]["terminal"]["actor"]
        self.assertEqual(terminal["logical"], terminal["origin"])
        self.assertNotEqual(terminal["logical"], terminal["target"])
        _, result = replay(route, finish=False)
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["followerMotions"], 1)

    def test_origin_cancellation_cannot_hide_movement_or_tile_drift(self):
        for fault in ("elapsed", "previous-tile", "previous-render", "current-tile",
                      "current-previous-tile", "current-render", "later-render"):
            with self.subTest(fault=fault):
                route, boundary = self.fixture(cancel_before_travel=True)
                old = route.records[boundary - 1]["samples"][0]["actors"][0]
                actor = route.records[boundary]["samples"][0]["actors"][0]
                if fault == "elapsed":
                    old["motionElapsed"] = actor["motionElapsed"] = 1
                elif fault == "previous-tile": old["engineObject"]["x"] += 1
                elif fault == "previous-render": old["engineObject"]["pos_x"] += 1
                elif fault == "current-tile": actor["engineObject"]["x"] += 1
                elif fault == "current-previous-tile": actor["engineObject"]["x_prev"] += 1
                elif fault == "current-render": actor["engineObject"]["pos_x"] += 1
                else:
                    route.records[boundary + 1]["samples"][0]["actors"][0]["engineObject"]["pos_x"] += 1
                _, result = replay(route, finish=False)
                self.assertTrue(result["failures"], fault)

    def test_partly_traveled_walk_cancels_at_unchanged_engine_origin(self):
        # Live b965add... frame865->866 cancels at elapsed1/8. Normalize
        # restores the current logical tile, not the partial render position.
        for elapsed in range(1, 4):
            with self.subTest(elapsed=elapsed):
                route, boundary = self.fixture(cancel_before_travel=True, cancel_elapsed=elapsed)
                prefix = deepcopy(route); prefix.records = prefix.records[:boundary + 1]
                _, result = replay(prefix, finish=False)
                self.assertEqual(result["failures"], [])
                self.assertEqual(result["followerMotions"], 0)
                _, result = replay(route, finish=False)
                self.assertEqual(result["failures"], [])
                self.assertEqual(result["followerMotions"], 1)

    def test_origin_after_boundary_is_a_missing_logical_advance(self):
        for elapsed in range(4, 8):
            with self.subTest(elapsed=elapsed):
                route, _ = self.fixture(cancel_before_travel=True, cancel_elapsed=elapsed)
                _, result = replay(route, finish=False)
                self.assertTrue(result["failures"])
                self.assertIn("path advance", result["failures"][0].get("detail", ""))

    def test_origin_cannot_ignore_a_native_path_advance(self):
        route, boundary = self.fixture(cancel_before_travel=True, cancel_elapsed=1)
        event = deepcopy(route.records[boundary]["events"][0])
        event["data"]["event"] = "PATH_ADVANCED"
        route.records[boundary]["events"].insert(0, event)
        sequence = 0
        for record in route.records:
            for e in record.get("events", []):
                if e["kind"] == "native":
                    sequence += 1
                    e["data"]["sequence"] = sequence
        _, result = replay(route, finish=False)
        self.assertTrue(result["failures"])
        self.assertIn("path advance", result["failures"][0].get("detail", ""))

    def test_origin_cancel_retains_exact_interior_travel_not_only_endpoints(self):
        route, boundary = self.fixture(cancel_before_travel=True, cancel_elapsed=3)
        route.records[boundary - 2]["samples"][0]["actors"][0]["engineObject"]["pos_x"] += 1
        _, result = replay(route, finish=False)
        self.assertTrue(result["failures"])
        self.assertIn("exact travel", result["failures"][0].get("detail", ""))

    def test_exact_canceled_handoff_retains_partial_motion_without_success_credit(self):
        route, boundary = self.fixture()
        prefix = deepcopy(route); prefix.records = prefix.records[:boundary + 1]
        meter, result = replay(prefix, finish=False)
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["followerMotions"], 0)
        self.assertIsNone(meter.recorder.current)
        canceled = result["handoffs"][0]["canceledMotion"]
        self.assertEqual([s["elapsed"] for s in canceled["motion"]["samples"]], list(range(7)))
        self.assertEqual(canceled["motion"]["commitBefore"], 0)
        self.assertNotIn("travelEnd", canceled["terminal"])
        _, result = replay(route, finish=False)
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["followerMotions"], 1)

    def test_canceled_handoff_missing_or_changed_evidence_fails(self):
        for fault in ("missing-cancel", "duplicate-cancel", "duplicate-control", "duplicate-context", "duplicate-rebound", "missing-control", "missing-context",
                      "missing-rebound", "wrong-pid", "changed-plan", "wrong-pose", "commit",
                      "reservation", "cancel-reason", "wrong-height", "wrong-clock", "next-motion-gap", "canceled-drift",
                      "current-tile", "previous-tile"):
            with self.subTest(fault=fault):
                route, index = self.fixture()
                row = route.records[index]; a = row["samples"][0]["actors"][0]
                names = {"missing-cancel": "MOTION_CANCELED", "duplicate-cancel": "MOTION_CANCELED",
                         "missing-control": "CONTROL_RETURNED", "missing-context": "CONTEXT_CHANGED",
                         "missing-rebound": "ACTOR_REBOUND", "duplicate-control": "CONTROL_RETURNED",
                         "duplicate-context": "CONTEXT_CHANGED", "duplicate-rebound": "ACTOR_REBOUND"}
                if fault in names:
                    event = next(e for e in row["events"] if e["data"]["event"] == names[fault])
                    if fault.startswith("duplicate-"):
                        row["events"].append(deepcopy(event))
                        sequence = 0
                        for record in route.records:
                            for e in record.get("events", []):
                                if e["kind"] == "native":
                                    sequence += 1
                                    e["data"]["sequence"] = sequence
                    else:
                        event["data"]["event"] = "PATH_ADVANCED"
                elif fault == "wrong-pid": a["subjectIdentity"] += 1
                elif fault == "changed-plan": a["target"]["x"] += 1
                elif fault == "wrong-pose": a["engineObject"]["pos_x"] -= 1
                elif fault == "current-tile": a["engineObject"]["x"] -= 1
                elif fault == "previous-tile": a["engineObject"]["x_prev"] -= 1
                elif fault == "wrong-height": a["engineObject"]["pos_y"] += 4096
                elif fault == "wrong-clock": row["events"][0]["data"]["actorFrame"] -= 1
                elif fault == "commit": a["commitSequence"] += 1
                elif fault == "reservation": a["reservationId"] = 448
                elif fault == "cancel-reason": a["lastCancelReason"] = 1
                elif fault == "next-motion-gap":
                    route.records[index + 5]["samples"][0]["actors"][0]["motionElapsed"] += 1
                elif fault == "canceled-drift":
                    route.records[index + 1]["samples"][0]["actors"][0]["engineObject"]["pos_x"] += 1
                _, result = replay(route, finish=False)
                self.assertTrue(result["failures"], fault)


class CadenceNativeTraceAbiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kinds, cls.control = actual_terminal_abi()

    def native_route(self, kind):
        route = Route(); route.setup_bind(); route.move(1)
        for record in route.records:
            for snapshot in record.get("samples", []):
                actor = snapshot["actors"][0]
                if actor["motionKind"] == "WALK": actor["motionKind"] = kind
            for event in record.get("events", []):
                data = event["data"]
                if data.get("event") == "CONTROL_RETURNED":
                    data["valueA"], data["valueB"] = self.control
                elif data.get("event") == "MOTION_STARTED": data["valueA"] = self.kinds[kind]
                elif data.get("event") in ("LOGICAL_COMMIT", "MOTION_FINISHED"): data["valueB"] = self.kinds[kind]
        return route

    def test_actual_c_trace_body_accepts_control_return(self):
        self.assertEqual(self.control, (0, 1))
        _, result = replay(self.native_route("WALK"), finish=False)
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["followerMotions"], 1)

    def test_actual_public_reposition_enum_accepts_trace(self):
        self.assertEqual(self.kinds["REPOSITION"], 5)
        _, result = replay(self.native_route("REPOSITION"), finish=False)
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["followerMotions"], 1)

    def test_synthetic_fixture_agrees_with_actual_terminal_body(self):
        route = Route(); route.setup_bind(); route.move(1)
        control = next(event["data"] for record in route.records for event in record.get("events", [])
                       if event["data"].get("event") == "CONTROL_RETURNED")
        self.assertEqual((control["valueA"], control["valueB"]), self.control)

    def test_old_reversed_control_and_wrong_reposition_are_rejected(self):
        for fault in ("reversed-control", "wrong-reposition"):
            with self.subTest(fault=fault):
                route = self.native_route("REPOSITION")
                for record in route.records:
                    for event in record.get("events", []):
                        data = event["data"]
                        if fault == "reversed-control" and data.get("event") == "CONTROL_RETURNED":
                            data["valueA"], data["valueB"] = self.control[::-1]
                        elif fault == "wrong-reposition" and data.get("event") == "MOTION_STARTED":
                            data["valueA"] = 4
                self.assertTrue(replay(route, finish=False)[1]["failures"])


class CadenceSetupAbsenceTests(unittest.TestCase):
    def route(self):
        route = Route(fainted=True)
        initial = route.records[0]["initialSnapshot"]
        initial["fieldControl"]["taskPointer"] = 0x02040000
        route.append("exit", phase="setup")
        row = route.records[-1]["samples"][0]
        for key in ("actors", "player", "party", "partyObservation", "context", "actorFrame", "selector", "fieldControl"):
            row.pop(key)
        row.update(fieldAvailable=False, observationErrors=[], fieldAvailability={
            "fieldPointer": 0, "actorStateMagic": 0x5353574F, "reasons": ["null-field-pointer"]})
        route.records[-1]["observedFieldFrames"] = 0
        route.context["mapId"] = 69
        route.p = player(8, 13)
        route.append("exit", phase="setup")
        spec = {"action": "exit", "departure": {"map": 33, "x": 0, "z": 0},
                "arrival": {"map": 69, "x": 8, "z": 13}, "maxFrames": 8}
        return route, spec

    def evaluate(self, route, spec):
        meter = UnmountedCadenceMeasurement(route.test, max_frames=32000, setup_transitions=[spec])
        for record in route.records:
            meter.observe_record(record)
        return meter

    def test_exact_doorway_retains_absence_without_actor_or_travel_credit(self):
        route, spec = self.route()
        result = self.evaluate(route, spec).result()
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["sampledFrames"], 2)
        self.assertEqual(result["nativeCycles"], 4)
        self.assertEqual(result["absentSetupFrames"], 1)
        self.assertEqual(result["observedFrames"], 0)
        self.assertEqual(result["activeMovementFrames"], 0)
        self.assertEqual(result["followerMotions"], 0)
        self.assertEqual(result["setupTransitions"][0]["arrivalFrame"], 2)
        self.assertFalse(result["ready"])

    def test_absence_default_still_fails(self):
        route, _ = self.route()
        self.assertTrue(replay(route, finish=False)[1]["failures"])

    def test_departure_arrival_lifecycle_and_clock_negative_controls(self):
        for fault in ("no-task", "wrong-departure", "wrong-arrival", "outside-setup", "stale-player",
                      "observer-error", "false-reason", "wrong-field-count", "lost-clock", "deadline", "new-action"):
            with self.subTest(fault=fault):
                route, spec = self.route()
                initial = route.records[0]["initialSnapshot"]
                absent = route.records[1]["samples"][0]
                arrival = route.records[2]["samples"][0]
                if fault == "no-task": initial["fieldControl"]["taskPointer"] = 0
                elif fault == "wrong-departure": initial["player"]["x"] = 9
                elif fault == "wrong-arrival": arrival["context"]["mapId"] = 67
                elif fault == "outside-setup": route.records[1].update(phase="observe", action="idle")
                elif fault == "stale-player": absent["player"] = player()
                elif fault == "observer-error": absent["observationErrors"] = [{"code": "trace-observation-failed"}]
                elif fault == "false-reason": absent["fieldAvailability"]["reasons"] = []
                elif fault == "wrong-field-count": route.records[1]["observedFieldFrames"] = 1
                elif fault == "lost-clock": absent["nativeCycle"] += 1
                elif fault == "deadline": spec["maxFrames"] = 1
                elif fault == "new-action": route.records[2]["action"] = "nurse"
                self.assertTrue(self.evaluate(route, spec).result()["failures"])

    def test_unsettled_arrival_cannot_close_transition(self):
        route, spec = self.route()
        route.records[2]["samples"][0]["fieldControl"]["taskPointer"] = 0x02040000
        meter = self.evaluate(route, spec)
        self.assertEqual(meter.result()["setupTransitions"], [])
        self.assertEqual(meter.finish()["failures"][0]["code"], "setup-transition-arrival-missing")

    def test_missing_arrival_is_not_a_transition_pass(self):
        route, spec = self.route()
        route.records.pop()
        self.assertEqual(self.evaluate(route, spec).finish()["failures"][0]["code"], "setup-transition-arrival-missing")


class CadenceTraceStatusTests(unittest.TestCase):
    def source_events(self):
        from tools.overworld.test_devtools_trace import NativeRing
        ring = NativeRing()
        tap = ring.tap()
        tap.start()
        for _ in range(16): ring.emit()
        before = [event for event in tap.sample(749) if event["kind"] == "native"]
        ring.emit()
        return before, tap.sample(750)

    def test_consumed_ring_reuse_from_real_trace_reader_is_not_missing_evidence(self):
        # Exact retained failure shape: test-2fc19971... frame750, stream1,
        # count1, unreadEventsLost0, after dense native sequences1..16.
        before, after = self.source_events()
        meter = UnmountedCadenceMeasurement(Route().test, max_frames=1000)
        meter._events(before, 749)
        self.assertEqual(after[0]["data"], dict(code="ring-overwrite", traceStream=1,
                         diagnosticOnly=True, count=1, unreadEventsLost=0))
        meter._events(after, 750)
        self.assertEqual(meter.trace_sequences, {1: 17})

    def test_loss_malformed_unknown_or_false_coverage_notice_cannot_pass(self):
        before, after = self.source_events()
        changes = [{"unreadEventsLost": 1}, {"unreadEventsLost": False},
            {"count": 0}, {"count": -1}, {"count": True}, {"count": 17},
            {"traceStream": 2}, {"traceStream": True}, {"diagnosticOnly": False},
            {"coverageComplete": False}, {"coverageComplete": True},
            {"code": "unread-events-lost"}, {"code": "sequence-reset"},
            {"code": "read-recovered"}, {"code": "trace-filter-changed"},
            {"code": "window-rearmed-externally"}, {"code": "worker-event-buffer-overflow"},
            {"code": "field-epoch-changed"}, {"code": "window-ended"}, {"code": "unknown"}]
        for change in changes:
            with self.subTest(change=change):
                meter = UnmountedCadenceMeasurement(Route().test, max_frames=1000)
                meter._events(before, 749)
                bad = deepcopy(after)
                bad[0]["data"].update(change)
                with self.assertRaisesRegex(ValueError, "coverage incomplete"):
                    meter._events(bad, 750)
                self.assertEqual(meter.trace_sequences, {1: 16})
        for key in after[0]["data"]:
            meter = UnmountedCadenceMeasurement(Route().test, max_frames=1000)
            meter._events(before, 749)
            bad = deepcopy(after)
            del bad[0]["data"][key]
            with self.subTest(missing=key), self.assertRaises(ValueError): meter._events(bad, 750)

    def test_no_loss_notice_does_not_hide_a_missing_native_sequence(self):
        before, after = self.source_events()
        meter = UnmountedCadenceMeasurement(Route().test, max_frames=1000)
        meter._events(before, 749)
        after[-1]["data"]["sequence"] = 18
        with self.assertRaisesRegex(ValueError, "semantic trace missing"):
            meter._events(after, 750)

    def epoch_case(self, previous=2):
        before, after = self.source_events()
        meter = UnmountedCadenceMeasurement(Route().test, max_frames=1000)
        meter._events(before, 749)
        current = (previous + 1) & 65535 or 1
        meter.latest = {"frame": 749, "fieldAvailable": True,
                        "context": {"fieldEpoch": previous, "mapGeneration": previous, "mapId": 33}}
        snapshot = {"frame": 750, "fieldAvailable": True,
                    "context": {"fieldEpoch": current, "mapGeneration": current, "mapId": 67}}
        after[0]["data"] = dict(code="field-epoch-changed", traceStream=1, diagnosticOnly=True,
                                 previousEpoch=previous, fieldEpoch=current, sequenceReset=False)
        event = after[1]["data"]
        event.update(event="CONTEXT_CHANGED", traceFieldEpoch=current, valueA=previous, valueB=current)
        event["actor"].update(fieldEpoch=previous, mapGeneration=previous)
        return meter, after, snapshot

    def test_coherent_epoch_increment_and_16_bit_wrap_keep_one_stream(self):
        for previous in (2, 65535):
            meter, events, snapshot = self.epoch_case(previous)
            meter._events(events, 750, snapshot)
            self.assertEqual(meter.trace_sequences, {1: 17})

    def test_context_drained_before_epoch_publication_keeps_old_capture_epoch(self):
        # Live test-4a2b1f... frame865: CONTEXT_CHANGED was drained at the
        # writer-return hook before the header changed; the notice came later
        # in the same completed game update. The actor handle is old in both
        # this case and the ordinary post-publication drain.
        for previous in (2, 65535):
            meter, events, snapshot = self.epoch_case(previous)
            events[1]["data"]["traceFieldEpoch"] = previous
            events.reverse()
            meter._events(events, 750, snapshot)
            self.assertEqual(meter.trace_sequences, {1: 17})

    def test_prepublication_witness_rejects_wrong_capture_epoch(self):
        for epoch in (1, 3, True):
            meter, events, snapshot = self.epoch_case()
            events[1]["data"]["traceFieldEpoch"] = epoch
            events.reverse()
            with self.subTest(epoch=epoch), self.assertRaises(ValueError):
                meter._events(events, 750, snapshot)

    def test_epoch_reset_missing_context_or_wrong_native_witness_fails(self):
        for fault in ("reset", "stream", "previous", "current", "generation", "absent", "missing-context",
                      "no-event", "event-values", "event-stream", "event-epoch", "event-handle",
                      "event-encoded-handle", "event-bool-stream", "event-gap"):
            with self.subTest(fault=fault):
                meter, events, snapshot = self.epoch_case()
                notice, native = events[0]["data"], events[1]["data"]
                if fault == "reset": notice["sequenceReset"] = True
                elif fault == "stream": notice["traceStream"] = 2
                elif fault == "previous": meter.latest["context"]["fieldEpoch"] = 1
                elif fault == "current": snapshot["context"]["fieldEpoch"] = 4
                elif fault == "generation": snapshot["context"]["mapGeneration"] = 4
                elif fault == "absent": snapshot["fieldAvailable"] = False
                elif fault == "missing-context": snapshot.pop("context")
                elif fault == "no-event": events.pop()
                elif fault == "event-values": native["valueB"] = 4
                elif fault == "event-stream": native["traceStream"] = 2
                elif fault == "event-epoch": native["traceFieldEpoch"] = 2
                elif fault == "event-handle": native["actor"]["fieldEpoch"] = 3
                elif fault == "event-encoded-handle": native["actorHandle"] += 1
                elif fault == "event-bool-stream": native["traceStream"] = True
                elif fault == "event-gap": native["sequence"] = 18
                with self.assertRaises(ValueError): meter._events(events, 750, snapshot)


class CadenceTests(unittest.TestCase):
    def test_retained_center_heal_waits_for_later_outdoor_native_confirmation(self):
        # Exact state/timing projection from session-3_xx63pt /
        # recording-a6286a6d0921.json. This tests the setup state seam, not a
        # complete route replay. The outdoor getter is a synthetic continuation.
        route = Route(fainted=True)
        route.frame = 733
        route.mon.update(personality=2046726716, level=6, maxHp=21)
        meter = UnmountedCadenceMeasurement(route.test, max_frames=2000)
        meter._snapshot(route.snapshot(), initial=True)
        old = dict(slot=1, field="hp", native=0, decoded=0, passed=True,
            personality=2046726716, species=155, frame=1027, decodedAtFrame=902,
            boundary="natural-GetMonData-return")
        for frame, hp, edge in ((1027, 0, 1), (1603, 21, 0), (1868, 21, 0)):
            route.frame = frame
            route.context["mapId"] = 69
            route.mon["hp"] = hp
            route.selector["newKeys"] = edge
            route.getters = [old]
            row = route.snapshot()
            meter._setup_frame(row, ["A"] if edge else [], *meter._party(row))
        route.frame = 1869
        route.context["mapId"] = 67
        row = route.snapshot()
        meter._setup_frame(row, [], *meter._party(row))
        self.assertEqual(meter.failures, [])
        self.assertEqual(meter.setup["healingObserved"]["frame"], 1603)
        self.assertIsNone(meter.setup["healed"])
        self.assertFalse(meter.result()["ready"])
        route.frame = 1870
        route.getters = [{**old, "native": 21, "decoded": 21, "frame": 1870, "decodedAtFrame": 1870}]
        row = route.snapshot()
        meter._setup_frame(row, ["Y"], *meter._party(row))
        self.assertEqual(meter.failures, [])
        self.assertEqual(meter.setup["healed"]["frame"], 1870)
        self.assertEqual(meter.setup["exitedCenter"], 1869)

    def test_delayed_heal_confirmation_full_stream_and_negative_controls(self):
        route = Route(fainted=True)
        route.setup_bind(heal=True)
        for record in route.records:
            for row in record.get("samples", [record["snapshot"]] if "snapshot" in record else []):
                for getter in row["partyObservation"]["nativeGetterChecks"]:
                    if row["frame"] < 4:
                        getter.update(native=0, decoded=0, frame=1, decodedAtFrame=1)
                    else:
                        getter.update(frame=4, decodedAtFrame=4)
        _, result = replay(route, finish=False)
        self.assertEqual(result["failures"], [])
        self.assertEqual(result["setup"]["healingObserved"]["frame"], 2)
        self.assertEqual(result["setup"]["healed"]["frame"], 4)
        self.assertEqual(result["setup"]["exitedCenter"], 3)
        self.assertEqual(result["setup"]["bound"], 5)
        self.assertFalse(result["ready"])  # Setup is not the 5000-frame route.
        for fault in ("first-outdoors", "wrong-mon", "no-confirmation", "old-frame", "old-decode",
                      "future-frame", "future-decode", "wrong-pid", "wrong-species", "wrong-slot",
                      "failed-check", "wrong-boundary", "wrong-hp", "no-A"):
            with self.subTest(fault=fault):
                bad = deepcopy(route)
                for record in bad.records:
                    rows = record.get("samples", [record["snapshot"]] if "snapshot" in record else [])
                    for row in rows:
                        if fault == "no-A": row["selector"]["newKeys"] &= ~1
                        if fault == "first-outdoors" and row["frame"] == 2: row["context"]["mapId"] = 33
                        if fault == "wrong-mon" and row["frame"] >= 2: row["party"][1]["personality"] += 1
                        if row["frame"] < 4: continue
                        for getter in row["partyObservation"]["nativeGetterChecks"]:
                            changes = {"no-confirmation": {"native": 0, "decoded": 0},
                                "old-frame": {"frame": 1, "decodedAtFrame": 1},
                                "old-decode": {"decodedAtFrame": 1},
                                "future-frame": {"frame": 99}, "future-decode": {"decodedAtFrame": 99},
                                "wrong-pid": {"personality": 987}, "wrong-species": {"species": 1},
                                "wrong-slot": {"slot": 0}, "failed-check": {"passed": False},
                                "wrong-boundary": {"boundary": "prepared"}, "wrong-hp": {"native": 1}}
                            getter.update(changes.get(fault, {}))
                _, result = replay(bad, finish=False)
                self.assertTrue(result["failures"], fault)
                self.assertIsNone(result["subject"], fault)
                self.assertFalse(result["ready"], fault)

    @classmethod
    def setUpClass(cls):
        cls.short = Route(); cls.short.setup_bind()
        for tile in range(1, 10): cls.short.move(tile)
        cls.long = Route(); cls.long.setup_bind()
        for tile in range(1, 161): cls.long.move(tile)

    def test_complete_exact_long_route(self):
        _, result = replay(self.long)
        self.assertTrue(result["passed"], result["failures"])
        self.assertFalse(result["acceptedProof"])
        self.assertEqual(result["activeMovementFrames"], 5120)
        self.assertEqual(result["followerMotions"], 20)
        self.assertEqual(result["distinctTiles"], 161)
        self.assertEqual(result["maps"], [33, 67])
        self.assertEqual(len(result["handoffs"]), 1)

    def test_short_success_is_not_long_proof_or_idle_padding(self):
        _, result = replay(self.short)
        self.assertFalse(result["passed"])
        self.assertEqual(result["activeMovementFrames"], 288)
        idle = Route(); idle.setup_bind()
        for _ in range(100): idle.append("idle")
        _, result = replay(idle)
        self.assertEqual(result["activeMovementFrames"], 0)

    def test_active_floor_and_held_route_conditions_are_not_inferred(self):
        route = deepcopy(self.long)
        route.records = [r for r in route.records if not r.get("samples")
                         or r["samples"][0]["frame"] <= 2 + 156 * 32]
        _, result = replay(route)
        self.assertEqual(result["activeMovementFrames"], 4992)
        self.assertFalse(result["passed"])
        route = deepcopy(self.long)
        template = deepcopy(route.test["actions"][1])
        for tile in range(1, 161):
            action = deepcopy(template); action["id"] = "released-tile-" + str(tile)
            route.test["actions"].append(action)
        for record in route.records:
            if record.get("action", "").startswith("route-"):
                record["action"] = "released-tile-" + str((record["samples"][0]["frame"] - 3) // 32 + 1)
        _, result = replay(route)
        self.assertEqual(result["activeMovementFrames"], 5120)
        self.assertEqual(result["heldCellCrossings"], 0)
        self.assertFalse(result["passed"])

    def test_normal_healing_then_selection_provenance(self):
        route = Route(fainted=True); route.setup_bind(heal=True)
        _, result = replay(route, finish=False)
        self.assertFalse(result["failures"], result["failures"])
        self.assertIsNotNone(result["setup"]["healed"])
        for label in ("stale-getter", "wrong-pid", "missing-input"):
            bad = deepcopy(route)
            for record in bad.records:
                for snapshot in record.get("samples", []):
                    if label == "missing-input": snapshot["selector"]["newKeys"] &= ~1
                    for receipt in snapshot["partyObservation"]["nativeGetterChecks"]:
                        if label == "stale-getter": receipt["frame"] = 0
                        if label == "wrong-pid": receipt["personality"] = 987
            _, result = replay(bad)
            self.assertFalse(result["passed"], label)
            self.assertTrue(result["evidenceGaps"], label)

    def test_same_species_replacement_wrong_role_and_missing_presentation_fail(self):
        for field, value in (("subjectIdentity", 987), ("role", "MOUNTED"), ("presentationAttached", False),
                             ("form", 2), ("level", 8), ("inputOwnership", 1)):
            route = deepcopy(self.short)
            route.records[14 if field == "inputOwnership" else 4]["samples"][0]["actors"][0][field] = value
            _, result = replay(route)
            self.assertTrue(result["failures"], field)

    def test_raw_native_interval_and_complete_frame_negative_controls(self):
        for mode in ("missing-cycle", "padded-native-count", "missing-frame", "field-absent", "queue-skip", "missing-admission", "duplicate-admission", "bad-native-target"):
            route = deepcopy(self.short)
            record = route.records[4]
            if mode == "missing-cycle": record["cycleIntervals"].pop()
            if mode == "padded-native-count":
                record["cycleIntervals"].insert(0, deepcopy(record["cycleIntervals"][0])); record["nativeCycles"] += 1
            if mode == "missing-frame": record["samples"][0]["frame"] += 1
            if mode == "field-absent": record["samples"] = []
            if mode == "queue-skip": record["cycleIntervals"][0]["completedGameFrame"] += 4
            if mode == "missing-admission": record["events"] = []
            if mode == "duplicate-admission": record["events"].insert(0, deepcopy(record["events"][0]))
            if mode == "bad-native-target": record["events"][0]["data"]["objectAfter"]["x"] = 99
            _, result = replay(route)
            self.assertTrue(result["failures"], mode)

    def test_actual_short_player_stutter_is_caught_before_long_floor(self):
        for mode in ("frozen", "reverse", "sideways", "no-admission", "slow-start", "late-settle"):
            route = deepcopy(self.short)
            frames = [r for r in route.records if r.get("action") == "route-0"]
            if mode in ("frozen", "reverse"):
                frames[5]["samples"][0]["player"]["pos_x"] = frames[4]["samples"][0]["player"]["pos_x"] - (1 if mode == "reverse" else 0)
            elif mode == "sideways": frames[5]["samples"][0]["player"]["pos_z"] += 1000
            elif mode == "no-admission":
                for record in frames[:4]:
                    record["events"] = [e for e in record["events"] if e["kind"] != "native-observation"]
                    record["samples"][0]["nativeObservation"].update(sequence=0, playerStepCount=0)
            elif mode == "slow-start":
                for record in frames[:4]: record["samples"][0]["player"]["pos_x"] = 32768
            else:
                for record in frames[31:38]:
                    record["samples"][0]["player"].update(pos_x=98304, x=1, flags=0x11)
                    record["events"] = [e for e in record["events"] if e["kind"] != "native-observation"]
                    record["samples"][0]["nativeObservation"].update(sequence=1, playerStepCount=1)
            _, result = replay(route, finish=False)
            self.assertTrue(result["failures"], mode)
            self.assertLess(result["observedFrames"], 40, mode)

    def test_cpu_hitch_uses_every_cycle_without_warmup(self):
        route = deepcopy(self.short)
        route.records[4]["cycleIntervals"][0]["cpuNs"] = 900000
        _, result = replay(route, finish=False)
        self.assertEqual(result["failures"][0]["code"], "host-process-cpu-hitch")
        self.assertEqual(result["cpu"]["hitchFrames"], [0])

    def test_diagnostic_host_hitch_continues_complete_window_but_never_passes(self):
        route=deepcopy(self.long);route.records[4]['cycleIntervals'][0]['cpuNs']=900000
        meter,result=replay(route,finish=False,diagnostic_continue_host_hitches=True)
        self.assertEqual(result['failures'],[])
        self.assertTrue(result['ready']);self.assertTrue(result['routeWindowReady'])
        self.assertEqual(result['activeMovementFrames'],5120)
        first=deepcopy(result['hostCpuViolation'])
        self.assertEqual(first['code'],'host-process-cpu-hitch')
        # A later reference median cannot erase the first measured violation.
        meter.route_cpu=[900000]*len(meter.route_cpu);meter._cpu_check()
        self.assertEqual(meter.result()['hostCpuViolation'],first)
        self.assertEqual(meter.result()['hostCpuLatest']['hitchCount'],0)
        final=meter.finish()
        self.assertFalse(final['passed']);self.assertFalse(final['ready']);self.assertFalse(final['acceptedProof'])
        self.assertTrue(final['routeWindowReady']);self.assertEqual(final['failures'][0],first)

    def test_diagnostic_no_hitch_never_grants_terminal_proof(self):
        _,result=replay(self.long,diagnostic_continue_host_hitches=True)
        self.assertFalse(result['passed']);self.assertFalse(result['ready'])
        self.assertEqual(result['failures'][0]['code'],'diagnostic-cadence-not-proof')

    def test_diagnostic_only_host_hitches_are_deferred(self):
        for value in (0,1,None,'true'):
            with self.assertRaisesRegex(ValueError,'must be boolean'):
                UnmountedCadenceMeasurement(self.short.test,max_frames=600,diagnostic_continue_host_hitches=value)
        meter=UnmountedCadenceMeasurement(self.short.test,max_frames=600,diagnostic_continue_host_hitches=True)
        meter.route_cpu=[100000]*20+[900000];meter._cpu_check()
        self.assertFalse(meter.failures)
        meter._fail('spawn-metadata-unavailable',{'species':163,'form':0})
        self.assertEqual(meter.progress_result()['state'],'failed')
        self.assertEqual(meter.finish()['failures'][0]['code'],'spawn-metadata-unavailable')

    def test_guest_queue_delay_fails_before_route_floor(self):
        route = Route(); route.setup_bind(); route.move(1)
        row = next(r for r in route.records if r.get("phase") == "observe" and r.get("samples"))
        row["nativeCycles"] = 4
        row["samples"][0]["nativeCycle"] += 2
        row["cycleIntervals"][0:0] = [deepcopy(row["cycleIntervals"][0]) for _ in range(2)]
        _, result = replay(route, finish=False)
        self.assertEqual(result["failures"][0]["code"], "guest-main-queue-delay")
        self.assertLess(result["observedFrames"], 4)
        _, diagnostic = replay(route, finish=False, diagnostic_continue_host_hitches=True)
        self.assertEqual(diagnostic['failures'][0]['code'],'guest-main-queue-delay')
        self.assertLess(diagnostic['observedFrames'],4)

    def test_follower_frozen_and_missing_terminal_receipt_fail(self):
        for mode in ("frozen", "terminal"):
            route = deepcopy(self.short)
            if mode == "frozen":
                route.records[7]["samples"][0]["actors"][0]["engineObject"]["pos_x"] = route.records[6]["samples"][0]["actors"][0]["engineObject"]["pos_x"]
            else:
                record = route.records[12]
                record["events"] = [e for e in record["events"] if e["data"].get("event") != "CONTROL_RETURNED"]
            _, result = replay(route, finish=False)
            self.assertTrue(result["failures"], mode)

    def test_transition_needs_exact_paired_handles_and_old_terminal(self):
        for mode in ("missing-context", "wrong-generation", "wrong-map-event"):
            route = deepcopy(self.long)
            record = next(r for r in route.records if any(e["data"].get("event") == "ACTOR_REBOUND" for e in r.get("events", [])))
            if mode == "missing-context":
                record["events"] = [e for e in record["events"] if e["data"].get("event") != "CONTEXT_CHANGED"]
            elif mode == "wrong-generation": record["samples"][0]["actors"][0]["handle"]["generation"] = 9
            else:
                next(e for e in record["events"] if e["data"].get("event") == "ACTOR_REBOUND")["data"]["valueA"] = 99
            _, result = replay(route, finish=False)
            self.assertTrue(result["failures"], mode)

    def test_budget_prepared_record_and_sticky_failure(self):
        with self.assertRaises(ValueError): UnmountedCadenceMeasurement(self.short.test, max_frames=0)
        route = deepcopy(self.short)
        route.records[4]["samples"][0]["prepared"] = True
        evaluator, result = replay(route, finish=False)
        original = deepcopy(result["failures"])
        evaluator.observe_record(self.short.records[5])
        self.assertEqual(evaluator.finish()["failures"], original)

    def test_real_installed_player_admission_receipt_feeds_same_replay(self):
        from tools.overworld.test_devtools_observer import Fixture
        route = deepcopy(self.short)
        with tempfile.TemporaryDirectory(prefix="cadence-admission-control-") as directory:
            fixture = Fixture(directory)
            fixture.player = player()
            fixture.map_id = 33
            fixture.player_pointer = 0x02030000
            fixture.admit_player_step(3)
            fixture.observer.completed_frame(3)
            receipt = fixture.observer.drain()[0]
            route.records[4]["events"][0] = receipt
            fixture.observer.close()
        _, result = replay(route, finish=False)
        self.assertFalse(result["failures"], result["failures"])
        self.assertEqual(result["playerMotions"], 9)


class PreparedCadenceSetupTests(unittest.TestCase):
    def test_actual_prepared_recipe_normalized_spawn_defaults_are_accepted(self):
        import json
        from tools.overworld.devtools_test_contract import validate_test
        root=Path(__file__).resolve().parents[2]
        value=json.loads((root/"tests/overworld/test-recipes/world.cyndaquil-prepared-setup.json").read_text())
        value["measurements"]=[{"kind":"unmounted-cadence-v1","subject":value["subjects"][0]["id"],"setupTransitions":[]}]
        test=validate_test(value)
        meter=UnmountedCadenceMeasurement(test,max_frames=test["budgets"]["maxFrames"])
        self.assertEqual(meter.mode,"prepared")
        spawn=next(a for a in test["setup"] if a["op"]=="spawn")
        self.assertEqual((spawn["args"]["form"],spawn["args"]["level"]),(0,5))

    def fixture(self):
        route=Route();route.mon["hp"]=0
        test=deepcopy(route.test);test["mode"]="prepared"
        for op,args in (("party",{"slot":1,"hp":30,"status":0}),
                        ("spawn",{"slot":1,"species":155,"role":"FOLLOWER"})):
            test["setup"].append({"id":op,"op":op,"args":args,
                "budget":{"maxFrames":600,"maxSeconds":120,"noProgressFrames":600}})
        meter=UnmountedCadenceMeasurement(test,max_frames=32000)
        meter.observe_record({"phase":"setup","initialSnapshot":route.snapshot()})
        commands=[]
        for frame,op in ((1,"party"),(2,"spawn")):
            route.frame=frame;route.mon["hp"]=30
            route.getters=[{"slot":1,"field":"hp","native":30,"decoded":30,"passed":True,
                "personality":123456,"species":155,"frame":frame,"decodedAtFrame":frame,
                "boundary":"natural-GetMonData-return"}]
            s=route.snapshot();s["prepared"]=True
            receipt={"snapshot":deepcopy(s),"events":[],"setupBoundary":{
                "eventsDrained":True,"traceSequences":{},"frame":frame,"nativeCycle":frame*2}}
            if op=="party":receipt.update(value={"slot":1,"action":"edit"},party=s["party"],personality=123456)
            else:receipt.update(lifecycle="prepared-native-follower-lifecycle",preparedOnly=True,
                requestedSubject={"slot":1,"role":"FOLLOWER",**{key:route.mon[key]
                    for key in ("species","personality","form","level")}})
            commands.append({"phase":"setup","action":op,"command":op,"receipt":receipt,"snapshot":s})
        return meter,commands

    def test_prepared_party_follower_readback_and_bind_exclude_setup_frames(self):
        meter,commands=self.fixture()
        for record in commands:meter.observe_record(record)
        s=commands[-1]["snapshot"]
        meter.observe_record({"phase":"observe","action":"bind","command":"bind",
                              "snapshot":s,"receipt":s["actors"][0]})
        result=meter.result()
        self.assertEqual(result["failures"],[])
        self.assertIsNotNone(result["subject"])
        self.assertEqual(result["activeMovementFrames"],0)
        self.assertEqual(result["nativeCycles"],0)
        self.assertEqual(len(result["preparedSetup"]),2)
        self.assertFalse(result["ready"])
        self.assertEqual(result["limits"]["activeFrames"],5000)

    def test_prepared_setup_bad_receipts_and_later_mutations_fail(self):
        for fault in ("undrained","clock","identity","hp","wrong-slot","wrong-role","duplicate","post-bind","stale-native-hp"):
            with self.subTest(fault=fault):
                meter,commands=self.fixture()
                if fault=="undrained":commands[0]["receipt"]["setupBoundary"]["eventsDrained"]=False
                elif fault=="clock":commands[0]["snapshot"]["nativeCycle"]=-1
                elif fault=="identity":commands[0]["snapshot"]["party"][1]["personality"]=9
                elif fault=="hp":commands[0]["receipt"]["party"][1]["hp"]=1
                elif fault=="wrong-slot":commands[0]["receipt"]["value"]["slot"]=0
                elif fault=="wrong-role":commands[1]["receipt"]["requestedSubject"]["role"]="MOUNTED"
                for record in commands:meter.observe_record(record)
                if fault=="duplicate":meter.observe_record(commands[-1])
                if fault in ("post-bind","stale-native-hp"):
                    s=deepcopy(commands[-1]["snapshot"])
                    if fault=="stale-native-hp":s["partyObservation"]["nativeGetterChecks"][0]["frame"]=0
                    meter.observe_record({"phase":"observe","action":"bind","command":"bind",
                                          "snapshot":s,"receipt":s["actors"][0]})
                    if fault=="post-bind":meter.observe_record(commands[0])
                self.assertTrue(meter.failures)

    def test_post_bind_prepared_tag_or_native_gap_cannot_reset_baseline(self):
        for fault in ("tag", "native-gap"):
            meter,commands=self.fixture()
            for record in commands:meter.observe_record(record)
            s=deepcopy(commands[-1]["snapshot"])
            meter.observe_record({"phase":"observe","action":"bind","command":"bind",
                                  "snapshot":s,"receipt":s["actors"][0]})
            s["frame"]+=1;s["nativeCycle"]+=2
            s["partyObservation"]["frame"]=s["frame"]
            s["nativeObservation"]["playerStepFrame"]=s["frame"]
            if fault=="tag":s["prepared"]=False
            else:s["nativeObservation"]["sequence"]+=1
            meter.observe_record({"phase":"observe","action":"idle","samples":[s],"events":[],
                "nativeCycles":2,"completedGameFrames":1,"observedFieldFrames":1,
                "cycleIntervals":[{"cpuNs":100000,"wallNs":150000,"completedGameFrame":2},
                                  {"cpuNs":100000,"wallNs":150000,"completedGameFrame":3}]})
            self.assertTrue(meter.failures)

    def test_prepared_declaration_rejects_other_mutations_or_observation_commands(self):
        for op,args,phase in (("party",{"slot":1,"species":155},"setup"),
                              ("spawn",{"slot":1,"species":155,"role":"MOUNTED"},"setup"),
                              ("party",{"slot":1,"hp":30},"actions")):
            route=Route();route.test["mode"]="prepared"
            route.test[phase].append({"id":"invalid","op":op,"args":args,"budget":{}})
            with self.assertRaises(ValueError):UnmountedCadenceMeasurement(route.test,max_frames=100)


if __name__ == "__main__":
    unittest.main()
