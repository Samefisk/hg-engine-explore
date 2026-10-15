"""Host-only checks for the saturated Route 30 headroom window; no emulator."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from tools.overworld import devtools_population_headroom_measurement as measurement
from tools.overworld.devtools_main_loop_probe import ENTRY_SITE, RETURN_SITE, SCOPE, WAIT_SCOPE
from tools.overworld.devtools_population_headroom_measurement import (
    ACTIONS, BUSY_CODE, BUSY_MESSAGE, FULL_CODE, FULL_MESSAGE, KIND, LOST_ENTRY_CODE, LOST_ENTRY_MESSAGE, MAX_SPAWN_RETRIES, MIN_WAIT_ARM9_TICKS,
    P1_WAIT_ARM9_TICKS, P5_WAIT_ARM9_TICKS, REQUIREMENT, SETUP, SPAWN_RETRY_FRAMES, SPAWNS,
    TEST, WINDOW_LOOPS, build_recipe, spawn_with_neutral_retry, wait_summary)
from tools.overworld.devtools_population_headroom_proof import (
    CLAIMS, FAULTS, PopulationHeadroomNegative, contract, measurements, validate_negative_result)
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.proof_adapters import get_adapter

ROOT = Path(__file__).resolve().parents[2]
RECIPE = json.loads((ROOT / f"tests/overworld/test-recipes/{TEST}.json").read_text())
PID = 2920357538
ROM, SAVE, PROFILE = "a" * 64, "f" * 64, "c" * 64
SOURCE = dict(contractVersion=1, romSha256=ROM, sourceSaveSha256=SAVE, profileSha256=PROFILE)
START_FRAME = 100
LOOP_TICKS = 2240760
CLOCK_SCOPE = "nds-scheduler-ticks-not-cpu-or-instructions"


def wait_for(after):
    """Deterministic synthetic idle ticks, well above every floor."""
    return 650_000 + after * 7919 % 100_000


def handle(slot):
    return {"value": (1 << 16) | slot, "slot": slot, "generation": 1,
            "fieldEpoch": 1, "mapGeneration": 1, "encounterGeneration": 1}


def actor(species, slot, identity, role, level):
    return {"handle": handle(slot), "subjectIdentity": identity, "species": species, "role": role,
            "form": 0, "level": level, "active": True, "presentationAttached": True,
            "identityVerified": True, "authorityGeneration": 1, "engineAnchorGeneration": 1,
            "presentationGeneration": 1, "engineIdentity": {"pointer": 0x02100000 + slot * 0x100}}


def displacement(frame, observe_start):
    """Signed sixteenths of a tile walked by `frame` under the UP/DOWN script, then neutral."""
    total, offset = 0, frame - observe_start
    for index in range(2 * measurement.WALK_REPEATS):
        held = max(0, min(offset - index * measurement.WALK_FRAMES, measurement.WALK_FRAMES))
        total += held * (-1 if index % 2 == 0 else 1)
    return total


class Timeline:
    """Frame numbers shared by snapshots and events of one synthetic run."""
    arm_frame = None
    observe_start = None

    @property
    def first(self):
        return self.arm_frame + 1


def snapshot(frame, *, wilds=len(SPAWNS), timeline=None, map_id=34):
    start = timeline.observe_start if timeline and timeline.observe_start is not None else 10**9
    walked = displacement(frame, start) if frame > start else 0
    tile = 361 + walked // 16
    previous = 361 + displacement(frame - 1, start) // 16 if frame > start else 361
    sample = {
        "frame": frame, "nativeCycle": 1000 + 2 * frame, "actorFrame": frame,
        "fieldAvailable": True, "observationBoundary": "main-task-queue-completion",
        "romSha256": ROM, "sourceSaveSha256": SAVE,
        "context": {"fieldEpoch": 1, "mapGeneration": 1, "mapId": map_id},
        "fieldControl": {"taskPointer": 0},
        "nativeObservation": dict(coverageComplete=True, installedBeforeBoot=True, eventsDropped=0,
                                  pendingUnframedEvents=0, profilesEvicted=0, error=None),
        "party": [dict(slot=2, personality=PID, species=56, identityVerified=True)],
        "player": dict(x=557, y=tile, x_prev=557, y_prev=previous, pos_x=(557 << 16) + 32768,
                       pos_z=(361 << 16) + 32768 + walked * 4096),
        "actors": [actor(56, 7, PID, "FOLLOWER", 3)],
    }
    for slot, (name, species, _, _) in zip(range(wilds), SPAWNS):
        sample["actors"].append(actor(species, slot, 1000 + slot, "WILD", 5))
    return sample


def pacing_event(frame, first, *, wait=None):
    after = frame - 1
    clock = dict(version=1, running=True, scope=CLOCK_SCOPE, arm9Timestamp=after * LOOP_TICKS,
                 arm7Timestamp=after * 100, frameSequence=after * 2)
    wait = wait_for(after) if wait is None else wait
    return dict(frame=frame, kind="native-observation", data=dict(
        sequence=after - first + 1, observation="stock-main-loop-pacing", loopId=after - first + 1,
        afterQueueFrame=after, flushedAtQueueFrame=frame, returnSite=RETURN_SITE, scope=SCOPE,
        diagnosticOnly=False, acceptedProof=False, setupMode="prepared", windowIndex=0,
        frameCounter=2, actorFrame=after, nativeCycle=1000 + after * 2, guestClock=clock,
        intervalFromPrevious=None if after == first else dict(
            arm9Ticks=LOOP_TICKS, arm7Ticks=100, frameSequence=2, actorFrames=1, nativeCycles=2),
        waitEntrySite=ENTRY_SITE, waitEntryArm9Timestamp=clock["arm9Timestamp"] - wait,
        waitArm9Ticks=wait, waitScope=WAIT_SCOPE))


def raw(timeline, action, phase, start, count, keys, wilds=len(SPAWNS)):
    samples = [snapshot(f, wilds=wilds, timeline=timeline) for f in range(start, start + count)]
    intervals = []
    for sample in samples:
        intervals.extend([dict(completedGameFrame=sample["frame"] - 1, cpuNs=1, wallNs=1),
                          dict(completedGameFrame=sample["frame"], cpuNs=1, wallNs=1)])
    events = []
    if timeline.arm_frame is not None:
        for sample in samples:
            # The probe window is inclusive, so one extra row follows the credited loops.
            if timeline.first + 1 <= sample["frame"] <= timeline.first + WINDOW_LOOPS + 1:
                events.append(pacing_event(sample["frame"], timeline.first))
    return dict(phase=phase, action=action, samples=samples, events=events,
                requestedInput=dict(frames=count, keys=keys, releaseAtEnd=False, diagnosticDetails=False),
                completedGameFrames=count, observedFieldFrames=count, nativeCycles=2 * count,
                cycleIntervals=intervals)


def chunked(timeline, action, phase, start, count, keys, wilds=len(SPAWNS)):
    """The job's step chunks: at most CHUNK_FRAMES completed frames per raw row."""
    from tools.overworld.devtools_jobs import TestJobs
    rows, done = [], 0
    while done < count:
        size = min(TestJobs.CHUNK_FRAMES, count - done)
        rows.append(raw(timeline, action, phase, start + done, size, keys, wilds))
        done += size
    return rows


def spawn_row(timeline, index, frame):
    name, species, _, _ = SPAWNS[index]
    sample = snapshot(frame, wilds=index + 1, timeline=timeline)
    wild = sample["actors"][-1]
    native = {key: wild["handle"][key] for key in
              ("slot", "generation", "fieldEpoch", "mapGeneration", "encounterGeneration")}
    receipt = dict(snapshot=deepcopy(sample), events=[], value=dict(
        species=species, slot=index, personality=wild["subjectIdentity"],
        entrySpawn=dict(frame=frame, receipt=dict(
            version=1, size=64, serial=index + 1, status=1, queued=0,
            actor={**native, "reserved": 0}))))
    return dict(phase="setup", action="spawn-" + name, command="spawn", receipt=receipt, snapshot=sample)


def records(*, refusals=None, tail=None):
    """The rows a job would retain. `refusals` maps spawn index -> busy count."""
    refusals = refusals or {}
    timeline = Timeline()
    rows = [dict(phase="setup", initialSnapshot=snapshot(START_FRAME, wilds=0, timeline=timeline))]
    frame = START_FRAME
    for name, op, args in SETUP:
        if op == "teleport":
            frame += 1
            sample = snapshot(frame, wilds=0, timeline=timeline)
            sample["player"].update(x=557, y=361, x_prev=557, y_prev=361)
            rows.append(dict(phase="setup", action=name, command=op, receipt={}, snapshot=sample))
        elif op == "step":
            count = args["frames"]
            rows.extend(chunked(timeline, name, "setup", frame + 1, count, args["keys"],
                                len(SPAWNS) if name == "population-settle16" else 0))
            frame += count
        elif op == "spawn":
            index = [n for n, *_ in SPAWNS].index(name.removeprefix("spawn-"))
            for _ in range(refusals.get(index, 0)):
                frame += 1
                rows.append(dict(phase="setup", action=name, command="spawn-refused", receipt=dict(
                    code=BUSY_CODE, message=BUSY_MESSAGE, events=[]),
                    snapshot=snapshot(frame, wilds=index, timeline=timeline)))
                rows.append(raw(timeline, name, "setup", frame + 1, SPAWN_RETRY_FRAMES, [], index))
                frame += SPAWN_RETRY_FRAMES
            frame += 1
            rows.append(spawn_row(timeline, index, frame))
        elif op == "bind":
            sample = snapshot(frame, timeline=timeline)
            rows.append(dict(phase="setup", action=name, command=op,
                             receipt=select_current_actor(sample, sample["actors"][0]), snapshot=sample))
        elif op == "main-loop-pacing.arm":
            timeline.arm_frame = frame
            sample = snapshot(frame, timeline=timeline)
            rows.append(dict(phase="setup", action=name, command=op, snapshot=sample, receipt=dict(
                probe=dict(armedAtQueueFrame=frame, firstObservedQueueFrame=frame + 1,
                           lastObservedQueueFrame=frame + 1 + WINDOW_LOOPS, guestMemoryWrites=0))))
    timeline.observe_start = frame
    for name, op, args in ACTIONS:
        count = args["frames"]
        rows.extend(chunked(timeline, name, "observe", frame + 1, count, args["keys"]))
        frame += count
    return rows


def evaluate(rows, fault=None):
    from tools.overworld.devtools_test_contract import TestEvaluator
    evaluator = TestEvaluator(RECIPE)
    evaluator.install_measurements({KIND: SOURCE})
    control = PopulationHeadroomNegative(fault) if fault else None
    for row in rows:
        if control is not None:
            row = control.mutate(row, evaluator.subjects)
        evaluator.observe_record(row)
        if evaluator.failures:
            break
    result = evaluator.finish()
    return result, control


def meter_result(rows, fault=None):
    result, control = evaluate(rows, fault)
    return result, result["measurements"][KIND], control


class RecipeAndRegistrationTests(unittest.TestCase):
    def test_committed_recipe_is_the_reviewed_recipe(self):
        self.assertEqual(RECIPE, build_recipe())
        self.assertEqual(RECIPE["requirements"], [REQUIREMENT])

    def test_exact_input_script_has_no_run_key_and_fixed_lengths(self):
        walk = [(f"{key.lower()}16-{index:02d}", 16, [key])
                for index in range(1, 25) for key in ("UP", "DOWN")]
        self.assertEqual([(n, a["frames"], a["keys"]) for n, o, a in ACTIONS],
                         walk + [("settle16", 16, [])])
        self.assertTrue(all("B" not in a["keys"] for _, o, a in ACTIONS if o == "step"))
        arm = next(a for n, o, a in SETUP if o == "main-loop-pacing.arm")
        self.assertEqual(arm, {"maxFrames": 768})
        self.assertEqual(WINDOW_LOOPS, 768)
        self.assertEqual(next(a for n, o, a in SETUP if o == "teleport"),
                         dict(map=34, x=557, z=361, facing=0))
        self.assertEqual([species for _, species, *_ in SPAWNS], [16, 16, 60, 60, 163, 167])
        self.assertTrue(all(spawn["level"] == 5 for _, op, spawn in SETUP if op == "spawn"))

    def test_registered_recipe_changes_are_rejected(self):
        for mutate in (lambda r: r["budgets"].update(minObservedFrames=599),
                       lambda r: r["actions"][0]["args"].update(keys=["UP", "B"]),
                       lambda r: r["setup"][-1]["args"].update(maxFrames=600),
                       lambda r: r["setup"][0]["args"].update(x=558)):
            changed = deepcopy(RECIPE)
            mutate(changed)
            with self.assertRaises(ValueError):
                from tools.overworld.devtools_test_contract import validate_test
                validate_test(changed)

    def test_adapter_contract_scenario_and_registry_agree(self):
        adapter = get_adapter(KIND)
        self.assertEqual(adapter.requirement, REQUIREMENT)
        self.assertEqual(adapter.claims, CLAIMS)
        self.assertEqual(adapter.faults, FAULTS)
        registry = json.loads((ROOT / "tools/overworld/runtime_proof_registry.json").read_text())
        shared = registry["sharedTests"][TEST]
        self.assertEqual(shared["evaluator"], KIND)
        self.assertEqual(shared["measurementContract"], contract())
        self.assertEqual(registry["measurementContracts"][REQUIREMENT], contract())
        self.assertEqual(registry["runners"][REQUIREMENT], list(CLAIMS))
        self.assertEqual(registry["runnerKinds"][REQUIREMENT], "controlled-case")
        self.assertEqual(shared["recipeSha256"], hashlib.sha256(
            (ROOT / f"tests/overworld/test-recipes/{TEST}.json").read_bytes()).hexdigest())
        self.assertEqual(shared["minimumObservedFrames"], 600)

    def test_floors_sit_between_the_measured_before_and_after_runs(self):
        # Route 30 pond bank, 120-frame UP/DOWN steps, no run key (old ROM, test3588).
        before = dict(minimum=14_000, p1=150_000, p5=231_000)      # old-ROM diagnostic
        after = dict(minimum=43_000, p1=204_000, p5=318_000)       # accepted-mode fixed ROM test3588
        for key, floor in (("minimum", MIN_WAIT_ARM9_TICKS), ("p1", P1_WAIT_ARM9_TICKS),
                           ("p5", P5_WAIT_ARM9_TICKS)):
            self.assertLess(before[key], floor, key)
            self.assertLess(floor, after[key], key)

    def test_percentiles_use_the_measured_index_definition(self):
        waits = list(range(1000, 1000 + 955))
        summary = wait_summary(list(reversed(waits)))
        self.assertEqual((summary["minimum"], summary["p1"], summary["p5"], summary["median"]),
                         (waits[0], waits[955 // 100], waits[955 // 20], waits[955 // 2]))
        self.assertEqual(wait_summary([])["count"], 0)


class PassingRunTests(unittest.TestCase):
    def test_unfaulted_copy_passes_and_reports_headroom(self):
        result, meter, _ = meter_result(records())
        self.assertEqual(result["failures"], [])
        self.assertTrue(result["passed"], result)
        self.assertEqual(meter["failures"], [])
        self.assertTrue(meter["passed"] and meter["ready"] and meter["closed"])
        self.assertFalse(meter["acceptedProof"])
        self.assertEqual(meter["observedFrames"], WINDOW_LOOPS)
        self.assertEqual(meter["headroom"]["waitSampleCount"], WINDOW_LOOPS)
        self.assertGreaterEqual(meter["headroom"]["minimum"], MIN_WAIT_ARM9_TICKS)
        self.assertEqual(meter["population"]["minimumActiveActors"], 7)
        self.assertEqual(meter["population"]["saturatedPercent"], 100)
        self.assertEqual(len(meter["population"]["spawned"]), 6)
        self.assertEqual(meter["population"]["spawnRetries"], 0)
        self.assertEqual(meter["population"]["naturalCreations"], 0)
        self.assertGreaterEqual(meter["player"]["steps"], 1)
        self.assertTrue(meter["player"]["settled"])
        self.assertEqual(meter["pacing"]["lateMainLoopCount"], 0)
        self.assertEqual(meter["pacing"]["maximumNativeCycles"], 2)
        self.assertEqual(meter["subjects"]["mankey"]["species"], 56)

    def test_proof_rows_pass_the_registered_contract(self):
        result, meter, _ = meter_result(records())
        rows = measurements(result, {"sessionId": "s", "sessionCleanup": {
            "sessionId": "s", "closed": True, "errors": []}})
        self.assertTrue(rows and all(row["passed"] for row in rows))
        by_claim = {}
        for row in rows:
            by_claim.setdefault(row["claim"], []).append(row["name"])
        self.assertEqual({k: v for k, v in by_claim.items()},
                         {claim: [r["name"] for r in rules] for claim, rules in contract().items()})
        with self.assertRaisesRegex(ValueError, "did not close cleanly"):
            measurements(result, {"sessionId": "s", "sessionCleanup": {
                "sessionId": "s", "closed": False, "errors": []}})

    def test_busy_native_queue_is_answered_with_neutral_frames_and_credits_nothing(self):
        result, meter, _ = meter_result(records(refusals={2: 2, 5: 1}))
        self.assertEqual(result["failures"], [])
        self.assertTrue(result["passed"], result)
        self.assertEqual(meter["population"]["spawnRetries"], 3)

    def test_a_queued_entry_lost_to_natural_spawn_work_is_retried_too(self):
        rows = records(refusals={1: 1})
        refusal = next(r for r in rows if r.get("command") == "spawn-refused")
        refusal["receipt"].update(code=LOST_ENTRY_CODE, message=LOST_ENTRY_MESSAGE)
        result, meter, _ = meter_result(rows)
        self.assertTrue(result["passed"], meter["failures"])
        self.assertEqual(meter["population"]["spawnRetries"], 1)

    def test_immediate_spawn_receipt_without_a_queued_entry_is_a_real_adopt(self):
        rows = records()
        for row in rows:
            if row.get("command") == "spawn":
                value = row["receipt"]["value"]
                value.pop("entrySpawn")
                value["requestedPersonality"] = value["personality"]
        result, meter, _ = meter_result(rows)
        self.assertTrue(result["passed"], meter["failures"])
        # The immediate form still has to name a current actor in that slot.
        next(r for r in rows if r.get("command") == "spawn")["receipt"]["value"]["slot"] = 5
        _, meter, _ = meter_result(rows)
        self.assertIn("ADOPT lacks one full current Actor", meter["failures"][0])

    def test_natural_refill_may_fill_slots_so_later_requests_are_already_full(self):
        # Natural Wild actors take slots 3..5 before the last three requests.
        rows = records()
        natural = [actor(16, slot, 5000 + slot, "WILD", 3) for slot in (3, 4, 5)]
        def with_natural(sample):
            sample["actors"] = [a for a in sample["actors"] if a["handle"]["slot"] not in (3, 4, 5)] + deepcopy(natural)
        out = []
        for row in rows:
            if row.get("command") == "spawn" and row["action"] in (
                    "spawn-poliwag-b", "spawn-hoothoot", "spawn-spinarak"):
                sample = row["snapshot"]
                with_natural(sample)
                row = dict(row, receipt=dict(populationFull=True, code=FULL_CODE, message=FULL_MESSAGE,
                                             events=[], snapshot=deepcopy(sample)))
            elif row.get("command") in ("bind", "main-loop-pacing.arm", "spawn") or "samples" in row:
                for sample in [row.get("snapshot")] + row.get("samples", []):
                    if sample and row.get("action") not in ("pond-settle16",) and sample["frame"] > 130:
                        with_natural(sample)
                if row.get("command") == "bind":
                    row["receipt"] = select_current_actor(row["snapshot"], row["snapshot"]["actors"][0])
            out.append(row)
        result, meter, _ = meter_result(out)
        self.assertTrue(result["passed"], meter["failures"])
        self.assertEqual(meter["population"]["alreadyFullRequests"], 3)
        self.assertEqual(len(meter["population"]["spawned"]), 3)
        self.assertGreaterEqual(meter["population"]["armedActiveActors"], 7)

    def test_a_population_full_claim_needs_a_really_full_population(self):
        rows = records()
        spawn = next(r for r in rows if r.get("action") == "spawn-spinarak")
        sample = spawn["snapshot"]
        sample["actors"].pop()
        spawn["receipt"] = dict(populationFull=True, code=FULL_CODE, message=FULL_MESSAGE,
                                events=[], snapshot=deepcopy(sample))
        _, meter, _ = meter_result(rows)
        self.assertIn("spawn lacks actual ADOPT", meter["failures"][0])

    def test_six_actors_are_saturated_and_the_seven_actor_share_is_informational(self):
        rows = records()
        for row in rows:
            for sample in row.get("samples", []):
                if sample["frame"] >= 300:
                    sample["actors"].pop()  # one Wild gone: six actors remain
        result, meter, _ = meter_result(rows)
        self.assertTrue(result["passed"], meter["failures"])
        population = meter["population"]
        self.assertEqual(population["requiredActiveActors"], 6)
        self.assertEqual(population["saturatedPercent"], 100)
        self.assertLess(population["sevenActorPercent"], 100)
        self.assertGreater(population["sevenActorLoops"], 0)

    def test_a_busy_follower_is_retried_too(self):
        from tools.overworld.devtools_population_headroom_measurement import FOLLOWER_MOTION_MESSAGE
        rows = records(refusals={3: 1})
        next(r for r in rows if r.get("command") == "spawn-refused")["receipt"].update(
            code=BUSY_CODE, message=FOLLOWER_MOTION_MESSAGE)
        result, meter, _ = meter_result(rows)
        self.assertTrue(result["passed"], meter["failures"])

    def test_a_startup_rejection_is_retried_too(self):
        from tools.overworld.devtools_population_headroom_measurement import STARTUP_CODE, STARTUP_MESSAGE
        rows = records(refusals={4: 1})
        next(r for r in rows if r.get("command") == "spawn-refused")["receipt"].update(
            code=STARTUP_CODE, message=STARTUP_MESSAGE)
        result, meter, _ = meter_result(rows)
        self.assertTrue(result["passed"], meter["failures"])

    def test_a_tile_whose_startup_never_works_is_skipped_and_saturation_still_decides(self):
        from tools.overworld.devtools_population_headroom_measurement import STARTUP_CODE, STARTUP_MESSAGE
        rows = records()
        for row in rows:
            if row.get("command") == "spawn" and row["action"] == "spawn-pidgey-b":
                row["receipt"] = dict(startupSkipped=True, code=STARTUP_CODE, message=STARTUP_MESSAGE,
                                      events=[], snapshot=deepcopy(row["snapshot"]))
        result, meter, _ = meter_result(rows)
        self.assertTrue(result["passed"], meter["failures"])
        self.assertEqual(meter["population"]["startupSkippedRequests"], 1)
        self.assertEqual(len(meter["population"]["spawned"]), 5)
        # A skip that is not the exact startup refusal is not accepted.
        rows = records()
        for row in rows:
            if row.get("command") == "spawn" and row["action"] == "spawn-pidgey-b":
                row["receipt"] = dict(startupSkipped=True, code="busy", message=BUSY_MESSAGE,
                                      events=[], snapshot=deepcopy(row["snapshot"]))
        _, meter, _ = meter_result(rows)
        self.assertIn("spawn lacks actual ADOPT", meter["failures"][0])

    def test_natural_creation_is_informational_only(self):
        rows = records()
        # A natural Wild appears in the last third of the window.
        for row in rows:
            for sample in row.get("samples", []):
                if sample["frame"] > 600:
                    sample["actors"].append(actor(16, 6, 4242, "WILD", 3))
        result, meter, _ = meter_result(rows)
        self.assertTrue(result["passed"], result)
        self.assertEqual(meter["population"]["naturalCreations"], 1)

    def test_extra_pacing_row_after_the_credited_window_is_ignored(self):
        rows = records()
        events = [e["data"] for row in rows for e in row.get("events", [])]
        self.assertEqual(len(events), WINDOW_LOOPS + 1)
        result, meter, _ = meter_result(rows)
        self.assertTrue(result["passed"], result)
        self.assertEqual(meter["observedFrames"], WINDOW_LOOPS)


class RejectedRunTests(unittest.TestCase):
    def reasons(self, fault):
        result, meter, control = meter_result(records(), fault)
        self.assertTrue(control.applied, fault)
        self.assertFalse(result["passed"], fault)
        validate_negative_result(result, fault)
        return result, meter

    def test_every_copied_fault_fails_for_its_own_reason(self):
        for fault in FAULTS:
            with self.subTest(fault=fault):
                self.reasons(fault)

    def test_each_fault_fails_only_its_own_expected_reason(self):
        expected = {
            "late-loop": "extra game frame", "low-idle-loop": "per-loop floor",
            "thin-headroom-tail": "5th percentile", "missing-wait-ticks": "lacks waitArm9Ticks",
            "under-saturated": "fewer than six", "short-window": "shorter than the required",
            "wrong-map": "Route30 field or source", "wrong-saved-mankey": "party identity"}
        for fault in FAULTS:
            name = fault.rsplit(":", 1)[1]
            with self.subTest(fault=name):
                _, meter, _ = meter_result(records(), fault)
                self.assertEqual(len(meter["failures"]), 1, meter["failures"])
                self.assertIn(expected[name], meter["failures"][0])
                for other, text in expected.items():
                    if other != name:
                        self.assertNotIn(text, meter["failures"][0], (name, other))

    def test_validate_negative_result_rejects_passes_and_wrong_reasons(self):
        result, _, _ = meter_result(records())
        with self.assertRaisesRegex(ValueError, "did not fail"):
            validate_negative_result(result, FAULTS[0])
        failed, _, _ = meter_result(records(), FAULTS[0])
        with self.assertRaisesRegex(ValueError, "unrelated reason"):
            validate_negative_result(failed, FAULTS[1])
        with self.assertRaisesRegex(ValueError, "unknown copied fault"):
            PopulationHeadroomNegative("population-headroom-v1:nope")

    def test_missing_pacing_sample_or_gap_fails_closed(self):
        rows = records()
        row = next(r for r in rows if any(e["data"]["afterQueueFrame"] == 150 for e in r.get("events", [])))
        row["events"] = [e for e in row["events"] if e["data"]["afterQueueFrame"] != 150]
        result, meter, _ = meter_result(rows)
        self.assertFalse(result["passed"])
        self.assertTrue(meter["failures"])

    def test_walk_that_stops_early_or_never_steps_fails(self):
        rows = records()[:-2]
        result, meter, _ = meter_result(rows)
        self.assertFalse(result["passed"])
        self.assertIn("complete exact input script", meter["failures"][0])

        still = records()
        for row in still:
            for sample in row.get("samples", []):
                sample["player"].update(y=361, y_prev=361, pos_z=(361 << 16) + 32768)
        result, meter, _ = meter_result(still)
        self.assertFalse(result["passed"])
        self.assertIn("no Player step", meter["failures"][0])

    def test_unsettled_final_tile_fails(self):
        rows = records()
        last = rows[-1]["samples"][-1]
        last["player"].update(y=362, y_prev=361, pos_z=last["player"]["pos_z"] + 1)
        result, meter, _ = meter_result(rows)
        self.assertFalse(result["passed"])
        self.assertIn("settled Route30 tile", meter["failures"][0])

    def test_wait_envelope_must_match_its_own_clocks_and_loop(self):
        for change, reason in (
                (lambda d: d.update(waitEntryArm9Timestamp=d["waitEntryArm9Timestamp"] + 1),
                 "differs from its own entry and return clocks"),
                (lambda d: d.update(waitArm9Ticks=-1), "lacks waitArm9Ticks"),
                (lambda d: d.update(waitEntrySite=ENTRY_SITE + 4), "differs from its own entry"),
                (lambda d: (d.update(waitArm9Ticks=LOOP_TICKS + 5),
                            d.update(waitEntryArm9Timestamp=d["guestClock"]["arm9Timestamp"] - LOOP_TICKS - 5)),
                 "exceeds its own loop interval")):
            with self.subTest(reason=reason):
                rows = records()
                row = next(r for r in rows if r.get("action") == "down16-01")
                change(row["events"][3]["data"])
                result, meter, _ = meter_result(rows)
                self.assertFalse(result["passed"])
                self.assertIn(reason, meter["failures"][0])

    def test_percentile_floors_are_enforced_separately(self):
        for wait, reason in ((P1_WAIT_ARM9_TICKS + 1, "5th percentile"), ):
            rows = records()
            changed = 0
            for row in rows:
                for event in row.get("events", []):
                    data = event["data"]
                    if changed < 40 and data["afterQueueFrame"] > 200:
                        data["waitArm9Ticks"] = wait
                        data["waitEntryArm9Timestamp"] = data["guestClock"]["arm9Timestamp"] - wait
                        changed += 1
            _, meter, _ = meter_result(rows)
            self.assertIn(reason, meter["failures"][0])
        rows = records()
        changed = 0
        for row in rows:
            for event in row.get("events", []):
                data = event["data"]
                if changed < 10 and data["afterQueueFrame"] > 200:
                    data["waitArm9Ticks"] = P1_WAIT_ARM9_TICKS - 1
                    data["waitEntryArm9Timestamp"] = data["guestClock"]["arm9Timestamp"] - data["waitArm9Ticks"]
                    changed += 1
        _, meter, _ = meter_result(rows)
        self.assertIn("1st percentile", meter["failures"][0])

    def test_ninety_percent_saturation_boundary(self):
        def with_missing(count):
            rows = records()
            frames = set(range(300, 300 + count))
            for row in rows:
                for sample in row.get("samples", []):
                    if sample["frame"] in frames:
                        sample["actors"].pop()
                        sample["actors"].pop()
            return meter_result(rows)
        result, meter, _ = with_missing(76)
        self.assertTrue(result["passed"], meter["failures"])
        self.assertEqual(meter["population"]["saturatedPercent"], 90)
        result, meter, _ = with_missing(77)
        self.assertFalse(result["passed"])
        self.assertIn("fewer than six", meter["failures"][0])

    def test_unsaturated_window_cannot_arm(self):
        rows = records()
        arm = next(r for r in rows if r.get("command") == "main-loop-pacing.arm")
        arm["snapshot"]["actors"].pop()
        arm["snapshot"]["actors"].pop()
        result, meter, _ = meter_result(rows)
        self.assertFalse(result["passed"])
        self.assertIn("not saturated when the window arms", meter["failures"][0])

    def test_refusal_rules_fail_closed(self):
        def run(change):
            rows = records(refusals={1: 1})
            change(rows)
            return meter_result(rows)[1]["failures"]
        refusal = lambda rows: next(r for r in rows if r.get("command") == "spawn-refused")
        self.assertIn("not the busy native queue", run(
            lambda rows: refusal(rows)["receipt"].update(code="spawn-rejected"))[0])
        self.assertIn("not the busy native queue", run(
            lambda rows: refusal(rows)["receipt"].update(message="native spawn lifecycle rejected this encounter"))[0])
        # The neutral chunk must follow, with exactly the declared frames.
        def drop_neutral(rows):
            rows.remove(next(r for r in rows if "samples" in r and r.get("action") == "spawn-pidgey-b"))
        self.assertIn("neutral frames are missing", run(drop_neutral)[0])
        # Twice refused in a row without neutral frames.
        def double(rows):
            rows.insert(rows.index(refusal(rows)) + 1, deepcopy(refusal(rows)))
        self.assertIn("refused twice", run(double)[0])
        # A chunk with another length is not the declared retry.
        def short(rows):
            chunk = next(r for r in rows if "samples" in r and r.get("action") == "spawn-pidgey-b")
            chunk["requestedInput"]["frames"] = 7
        self.assertIn("exact neutral frames", run(short)[0])

    def test_refusal_snapshot_may_lag_the_native_clock_within_its_bound(self):
        # Live: the refused request ran a native cycle past the snapshot's cycle.
        for lag, passes in ((1, True), (measurement.MAX_REFUSAL_CYCLES, True),
                            (measurement.MAX_REFUSAL_CYCLES + 1, False), (-1, False)):
            with self.subTest(lag=lag):
                rows = records(refusals={0: 1})
                at = next(i for i, r in enumerate(rows) if r.get("command") == "spawn-refused")
                chunk = rows[at + 1]
                for sample in chunk["samples"]:
                    sample["nativeCycle"] += lag
                rows[at + 1] = chunk
                # Later rows continue from the chunk's own samples.
                shift = lag
                for row in rows[at + 2:]:
                    for sample in row.get("samples", []) + [row.get("snapshot") or {},
                                                            (row.get("receipt") or {}).get("snapshot") or {}]:
                        if "nativeCycle" in sample:
                            sample["nativeCycle"] += shift
                    for event in row.get("events", []):
                        data = event["data"]
                        if "nativeCycle" in data:
                            data["nativeCycle"] += shift
                result, meter, _ = meter_result(rows)
                self.assertEqual(result["passed"], passes, meter["failures"])
                if not passes:
                    self.assertIn("native clock", meter["failures"][0])

    def test_spawn_must_be_a_real_adopt(self):
        rows = records()
        spawn = next(r for r in rows if r.get("action") == "spawn-hoothoot")
        spawn["receipt"]["value"]["entrySpawn"]["receipt"]["status"] = 0
        _, meter, _ = meter_result(rows)
        self.assertIn("spawn lacks actual ADOPT", meter["failures"][0])

    def test_teleport_must_reach_the_pond_bank(self):
        rows = records()
        next(r for r in rows if r.get("command") == "teleport")["snapshot"]["player"]["x"] = 565
        _, meter, _ = meter_result(rows)
        self.assertIn("did not reach the pond bank", meter["failures"][0])

    def test_lost_native_data_and_mounting_fail(self):
        for path, reason in ((lambda s: s["nativeObservation"].update(eventsDropped=1), "native reader lost data"),
                             (lambda s: s["actors"][0].update(role="MOUNTED"), "mounted")):
            with self.subTest(reason=reason):
                rows = records()
                path(next(r for r in rows if r.get("action") == "down16-01")["samples"][5])
                _, meter, _ = meter_result(rows)
                self.assertTrue(meter["failures"])


class SpawnRetryTests(unittest.TestCase):
    class Busy(Exception):
        code = BUSY_CODE

    def test_only_a_busy_queue_is_retried_and_the_retry_is_bounded(self):
        calls, seen = [], []
        def spawn():
            calls.append(1)
            if len(calls) < 3:
                raise self.Busy("DevtoolsFailure: " + BUSY_MESSAGE)
            return "adopted"
        self.assertEqual(spawn_with_neutral_retry(spawn, lambda e: seen.append("refused"),
                                                  lambda: seen.append("neutral")), "adopted")
        self.assertEqual(seen, ["refused", "neutral", "refused", "neutral"])

        class Other(Exception):
            code = "spawn-rejected"
        def rejected():
            raise Other("native spawn lifecycle rejected this encounter")
        with self.assertRaises(Other):
            spawn_with_neutral_retry(rejected, lambda e: self.fail("refusal"), lambda: self.fail("neutral"))

        class WrongText(Exception):
            code = BUSY_CODE
        def other_busy():
            raise WrongText("prepared event retention is already active")
        with self.assertRaises(WrongText):
            spawn_with_neutral_retry(other_busy, lambda e: self.fail("refusal"), lambda: self.fail("neutral"))

        class Lost(Exception):
            code = LOST_ENTRY_CODE
        outcomes = [Lost("DevtoolsFailure: " + LOST_ENTRY_MESSAGE), "ok"]
        def lost_then_ok():
            item = outcomes.pop(0)
            if item == "ok":
                return "adopted"
            raise item
        seen.clear()
        self.assertEqual(spawn_with_neutral_retry(lost_then_ok, lambda e: seen.append("refused"),
                                                  lambda: seen.append("neutral")), "adopted")
        self.assertEqual(seen, ["refused", "neutral"])

        count = []
        def always():
            count.append(1)
            raise self.Busy(BUSY_MESSAGE)
        with self.assertRaises(self.Busy):
            spawn_with_neutral_retry(always, lambda e: None, lambda: None)
        self.assertEqual(len(count), MAX_SPAWN_RETRIES + 1)


class StartupSkipTests(unittest.TestCase):
    def test_startup_rejection_is_skipped_only_after_its_own_bound(self):
        from tools.overworld.devtools_population_headroom_measurement import (
            MAX_STARTUP_REFUSALS, STARTUP_CODE, STARTUP_MESSAGE)
        class Rejected(Exception):
            code = STARTUP_CODE
        calls, refused, neutral = [], [], []
        def spawn():
            calls.append(1)
            raise Rejected("DevtoolsFailure: " + STARTUP_MESSAGE)
        out = spawn_with_neutral_retry(spawn, refused.append, lambda: neutral.append(1),
                                       None, lambda error: "skipped")
        self.assertEqual(out, "skipped")
        self.assertEqual(len(calls), MAX_STARTUP_REFUSALS + 1)
        self.assertEqual(len(refused), MAX_STARTUP_REFUSALS)
        # Without a skip handler it keeps retrying to the overall bound and then raises.
        calls.clear()
        with self.assertRaises(Rejected):
            spawn_with_neutral_retry(spawn, lambda e: None, lambda: None)
        self.assertEqual(len(calls), MAX_SPAWN_RETRIES + 1)


class JobWiringTests(unittest.TestCase):
    """The runner side of the busy-queue retry, with no emulator and no evaluator."""

    def jobs(self, outcomes):
        import io
        import threading
        import time
        from types import SimpleNamespace
        from unittest.mock import Mock
        from tools.overworld.devtools_jobs import TestJobs
        events = [{"frame": 5, "kind": "native-observation", "data": {"sequence": 1}}]
        class Busy(Exception):
            code = BUSY_CODE
            details = {"preparedRetainedEvents": events}
        worker = Mock()
        worker.call.side_effect = lambda op, args=None: (
            {"frame": 10, "samples": []} if op == "snapshot" else
            {"completedGameFrames": SPAWN_RETRY_FRAMES, "samples": [{"frame": n} for n in range(SPAWN_RETRY_FRAMES)],
             "snapshot": {"frame": 99}, "events": []})
        service = SimpleNamespace(lock=threading.RLock(), worker=worker, _observe=Mock())
        jobs = TestJobs.__new__(TestJobs)
        jobs.service, jobs.cancel_event = service, threading.Event()
        queue = list(outcomes)
        def command(op, args):
            outcome = queue.pop(0)
            if outcome == "busy":
                raise Busy("DevtoolsFailure: " + BUSY_MESSAGE)
            if outcome == "other":
                error = Busy("DevtoolsFailure: native spawn lifecycle rejected this encounter")
                error.code = "spawn-rejected"
                raise error
            return {"snapshot": {"frame": 11}}
        jobs._command = command
        evaluator = Mock()
        evaluator.observe_record.return_value = {"state": "running"}
        stream = io.StringIO()
        test = {"budgets": {"maxSeconds": 100}}
        action = {"id": "spawn-pidgey-a", "budget": {"maxSeconds": 100}}
        run = lambda: jobs._spawn_after_busy_queue(
            "spawn", {}, "setup", action, test, time.monotonic(), time.monotonic(), stream, evaluator)
        return run, worker, evaluator, stream

    def test_busy_queue_retains_refusal_then_exactly_eight_neutral_frames_then_repeats(self):
        run, worker, evaluator, stream = self.jobs(["busy", "busy", "ok"])
        self.assertEqual(run(), {"snapshot": {"frame": 11}})
        rows = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual([r.get("command", "chunk") for r in rows],
                         ["spawn-refused", "chunk", "spawn-refused", "chunk"])
        self.assertEqual(rows[0]["receipt"], {"code": BUSY_CODE, "message": BUSY_MESSAGE,
                                              "events": [{"frame": 5, "kind": "native-observation",
                                                          "data": {"sequence": 1}}]})
        self.assertEqual(rows[1]["requestedInput"], dict(
            frames=SPAWN_RETRY_FRAMES, keys=[], releaseAtEnd=False, diagnosticDetails=False))
        self.assertEqual(rows[1]["action"], "spawn-pidgey-a")
        self.assertNotIn("snapshot", rows[1])
        self.assertEqual([c.args[0] for c in worker.call.call_args_list],
                         ["snapshot", "step", "snapshot", "step"])
        self.assertEqual(evaluator.observe_record.call_count, 4)

    def test_other_failures_and_failed_observation_stop_the_job(self):
        run, worker, evaluator, stream = self.jobs(["other"])
        with self.assertRaises(Exception) as caught:
            run()
        self.assertEqual(caught.exception.code, "spawn-rejected")
        self.assertEqual(stream.getvalue(), "")
        worker.call.assert_not_called()
        run, worker, evaluator, stream = self.jobs(["busy", "ok"])
        evaluator.observe_record.return_value = {"state": "failed"}
        with self.assertRaisesRegex(RuntimeError, "spawn-refusal-observation-failed"):
            run()

    def test_short_neutral_batch_is_incomplete_evidence(self):
        run, worker, evaluator, stream = self.jobs(["busy", "ok"])
        worker.call.side_effect = lambda op, args=None: (
            {"frame": 10} if op == "snapshot" else
            {"completedGameFrames": 3, "samples": [{"frame": 1}] * 3, "events": []})
        with self.assertRaisesRegex(RuntimeError, "incomplete-frame-evidence"):
            run()


if __name__ == "__main__":
    unittest.main()
