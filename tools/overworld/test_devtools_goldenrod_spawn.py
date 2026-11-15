"""Host controls for T79's native-birth predicate; no live game acceptance."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.overworld.devtools_goldenrod_spawn_measurement import (
    BEHIND, RAISED, UNDERGROUND, CASES, UNDERGROUND_FLOOR, source_inputs, witnesses,
    GoldenrodSpawnMeasurement)
from tools.overworld.devtools_goldenrod_spawn_proof import GoldenrodSpawnNegative, validate_negative_result
from tools.overworld.devtools_spawn_surface_measurement import check_natural_water_surface
from tools.overworld.test_devtools_spawn_priority import water_fixture
from tools.overworld.devtools_test_contract import validate_test


def fixture(kind, *, canopy=False, target=None):
    spawn, snapshot = water_fixture()
    species = 52 if kind == BEHIND else 198 if canopy else 519 if kind == RAISED else 19
    m = CASES[kind]["start"][0]
    target = list(target or ((374,359) if kind == BEHIND else (6,19) if kind == UNDERGROUND else (339,343)))
    mask = 0x801 if kind == BEHIND else 68 if canopy else 65 if kind == RAISED else 1
    spawn.update(terrain=0, position=target, sequence=3)
    spawn["startup"] = dict(locomotion=7, target=target, origin=target)
    spawn["preparedEncounter"]["species"] = species
    spawn["worldContext"]["mapId"] = m
    spawn["publicSubject"]["species"] = species
    snapshot["context"]["mapId"] = m
    snapshot["frame"] = 10
    actor = snapshot["actors"][0]
    actor.update(species=species, controllerState=0)
    actor["sourceIdentity"].update(species=species, map_id=m)
    actor["engineIdentity"].update(object_map_id=m,current_map_id=m,spawn_map_id=m)
    actor["engineObject"].update(x=target[0],y=target[1],pos_x=(target[0]<<16)+0x8000,
        pos_z=(target[1]<<16)+0x8000,movement_cmd=255)
    h = spawn["initialLandingHeight"]
    h.update(sourceIdentity=deepcopy(actor["sourceIdentity"]), engineIdentity=deepcopy(actor["engineIdentity"]),
        engineIdentityAfter=deepcopy(actor["engineIdentity"]), worldContext=deepcopy(spawn["worldContext"]),
        preparedEncounter=deepcopy(spawn["preparedEncounter"]), target=target)
    h["surfaceQuery"]["point"] = target
    for pose in (h["positionBefore"],h["positionAfter"],h["heightRefresh"]["positionBefore"],h["heightRefresh"]["positionAfter"]):
        pose.update(x=target[0],y=target[1],pos_x=(target[0]<<16)+0x8000,pos_z=(target[1]<<16)+0x8000)
    word = UNDERGROUND_FLOOR.get(tuple(target),0) if kind == UNDERGROUND else 0
    for name in ("loadedTerrainBefore","loadedTerrain"):
        cell = h[name]["cell"]
        cell.update(x=target[0],y=target[1],attribute=word,behavior=word&255,terrain_class=(word>>8)&127)
        cell["provenance"].update(rawWord=word, landDataId=41 if kind==BEHIND else 511 if kind==UNDERGROUND else 39)
    if kind == RAISED:
        hit = dict(height=0x30000 if canopy else 0x50000,surfaceId=0xFFFE if canopy else 0x100,surfaceType=4 if canopy else 0,nodeId=0)
        h["surfaceQuery"].update(returnValue=1,hit=hit)
        h["heightSource"] = "native-plus-catalog-offset" if canopy else "catalog-surface"
        h["heightRefresh"]["positionAfter"]["pos_y"] = 0x1000
        y = 0x31000 if canopy else 0x50000
        h["positionAfter"]["pos_y"] = actor["engineObject"]["pos_y"] = y
    request,result=bytearray(44),bytearray(216)
    request[0:2]=species.to_bytes(2,"little");request[2:4]=m.to_bytes(2,"little");request[8]=spawn["preparedEncounter"]["level"]
    result[52:54]=mask.to_bytes(2,"little");result[54:56]=(0xBFF).to_bytes(2,"little")
    source=dict(contractVersion=1,profileSha256="a"*64,catalogSha256="b"*64,
        behindTopology=[dict(target=[374,359],landDataId=41,roofLocal=[22,8],roofSource="declared-host-fixture")])
    final=spawn["finalization"]["receipt"]
    final.update(finalizationId=7, spawnAttemptId=1, querySerial=1, nativeOwner="Query.NativeFinalize",
        worldContext=deepcopy(spawn["worldContext"]), returnWorldContext=deepcopy(spawn["worldContext"]),
        inputEncounter=deepcopy(spawn["preparedEncounter"]),resolverReceipts=[
        dict(finalizationId=7,inputEncounter=deepcopy(spawn["preparedEncounter"]),requestHex=request.hex(),
             resultHex=result.hex(),sourceSha256=source["profileSha256"],resolved=True)])
    prepared = bytearray(260)
    encounter = spawn["preparedEncounter"]
    prepared[12:20] = (encounter["personality"].to_bytes(4,"little")
                      + encounter["species"].to_bytes(2,"little") + bytes((encounter["form"],encounter["level"])))
    prepared[36:252] = result
    final["queueAfter"] = dict(runtime=0x02210000, preparedPointer=spawn["preparedPointer"],
                               serial=1, terrain=0, preparedHex=prepared.hex())
    creation=dict(sequence=3,frame=1,species=species,insideSnapshotWindow=True,handle=deepcopy(spawn["publicSubject"]["handle"]))
    report=dict(naturalAttempts=[dict(creations=[creation],spawnAttemptId=1)],quality=dict(nativeCoverageComplete=True))
    events=[dict(frame=1,kind="native-observation",data=deepcopy(dict(observation="spawn-finalized",**{k:v for k,v in final.items() if k!="observation"}))),
            dict(frame=1,kind="native-observation",data=spawn)]
    return report,[snapshot],events,source


def cached_fixture(kind):
    report, snapshots, events, source = fixture(kind)
    preparation = deepcopy(events[0])
    preparation["data"].update(sequence=1, returnValue=0)
    final = events[-1]["data"]["finalization"]["receipt"]
    final.update(sequence=2, finalizationId=8, resolverReceipts=[])
    events = [preparation, dict(frame=1,kind="native-observation",data=deepcopy(final)), events[-1]]
    return report, snapshots, events, source


def check(kind, data):
    return witnesses(kind, *data)


class GoldenrodNativeSpawnTests(unittest.TestCase):
    def test_setup_preparation_can_support_only_the_same_observed_attempt(self):
        from tools.overworld.devtools_goldenrod_spawn_proof import faults
        for kind in CASES:
            report,samples,events,source=cached_fixture(kind)
            self.assertTrue(witnesses(kind,report,samples,events[1:],source,
                                      setup_finalizers=events[:1])["landings"])
            with self.assertRaisesRegex(ValueError,"single initial profile preparation"):
                witnesses(kind,report,samples,events[1:],source)
            with self.assertRaisesRegex(ValueError,"no required natural Goldenrod birth"):
                witnesses(kind,dict(naturalAttempts=[],quality={}),samples,[],source,
                          setup_finalizers=events)
            for fault in faults(kind):
                negative=GoldenrodSpawnNegative(kind,fault)
                preparation=negative.mutate(dict(phase="setup",events=events[:1]),{})
                observed=negative.mutate(dict(phase="observe",events=events[1:]),{})
                with self.subTest(kind=kind,fault=fault),self.assertRaises(ValueError) as error:
                    witnesses(kind,report,samples,observed["events"],source,
                              setup_finalizers=preparation["events"])
                validate_negative_result(kind,dict(passed=False,failures=[str(error.exception)]),fault)

    def test_idle_away_from_birth_cannot_replace_same_target_terminal(self):
        report,samples,events,source=cached_fixture(BEHIND)
        away=deepcopy(samples[0]);away["frame"]-=1
        away["actors"][0]["engineObject"]["x"]+=1
        away["actors"][0]["engineObject"]["pos_x"]+=65536
        self.assertTrue(witnesses(BEHIND,report,[away]+samples,events,source)["landings"])
        with self.assertRaisesRegex(ValueError,"no required natural Goldenrod birth"):
            witnesses(BEHIND,report,[away],events,source)

    def test_one_initial_preparation_is_reused_by_same_attempt_constructor(self):
        from tools.overworld.devtools_goldenrod_spawn_proof import faults
        for kind in CASES:
            self.assertTrue(check(kind,cached_fixture(kind))["landings"])
            for fault in faults(kind):
                with self.subTest(kind=kind,fault=fault):
                    report,samples,events,source=cached_fixture(kind)
                    negative=GoldenrodSpawnNegative(kind,fault)
                    changed=negative.mutate(dict(phase="observe",events=events),{})
                    self.assertTrue(negative.applied)
                    with self.assertRaises(ValueError) as error:
                        witnesses(kind,report,samples,changed["events"],source)
                    validate_negative_result(kind,dict(passed=False,failures=[str(error.exception)]),fault)

    def test_warp_settle_excludes_transient_follower_until_strict_bind(self):
        from tools.overworld.test_devtools_goldenrod_follower import sample
        from tools.overworld.devtools_records import select_current_actor
        kind = BEHIND
        test = json.loads((ROOT / f"tests/overworld/test-recipes/{CASES[kind]['test']}.json").read_text())
        source = source_inputs(ROOT)
        meter = GoldenrodSpawnMeasurement(test, source)
        initial = sample(100, player_z=366, tick=None)
        self.assertEqual(meter.observe_record(dict(phase="setup", initialSnapshot=initial))["failures"], [])
        transient = deepcopy(initial)
        transient.update(frame=101, nativeCycle=101)
        transient["player"].update(x=368, x_prev=368, pos_x=(368 << 16) + 32768)
        transient["selector"].update(heldKeys=0, newKeys=0, physicalPressed=0, simulatedKeys=0)
        transient["actors"][0]["identityVerified"] = False
        transient["actors"][0]["engineIdentity"]["active"] = False
        warp = dict(phase="setup", action="natural-window", command="teleport", snapshot=transient,
            receipt=dict(preparedOnly=True, snapshot=deepcopy(transient),
                         setupBoundary=dict(eventsDrained=True, frame=101, nativeCycle=101)))
        self.assertEqual(meter.observe_record(warp)["failures"], [])
        pending = deepcopy(meter)
        skipped = pending.observe_record(dict(phase="setup", action="bind-current-field", command="bind",
            snapshot=transient, receipt=initial["actors"][0]))
        self.assertIn("skipped its unsettled follower", repr(skipped["failures"]))
        samples = []
        for frame in range(102,126):
            current = deepcopy(transient)
            current.update(frame=frame, nativeCycle=frame)
            current["partyObservation"]["frame"] = frame
            if frame == 125:
                current["actors"][0]["identityVerified"] = True
                current["actors"][0]["engineIdentity"]["active"] = True
            samples.append(current)
        settle = dict(phase="setup", action="warp-settle", requestedInput=dict(keys=[]),
            completedGameFrames=24, nativeCycles=24, observedFieldFrames=24, samples=samples,
            events=[], cycleIntervals=[dict(completedGameFrame=s["frame"], cpuNs=1, wallNs=1) for s in samples])
        broken = deepcopy(meter)
        lost = deepcopy(settle); lost["samples"][0]["nativeObservation"]["coverageComplete"] = False
        self.assertIn("coverage is incomplete", repr(broken.observe_record(lost)["failures"]))
        self.assertEqual(meter.observe_record(settle)["failures"], [])
        self.assertEqual((meter.observed_frames, meter.snapshots, meter.setup_index), (0, [], 2))
        bind = dict(phase="setup", action="bind-current-field", command="bind", snapshot=samples[-1],
                    receipt=select_current_actor(samples[-1], samples[-1]["actors"][0]))
        stale = deepcopy(meter)
        invalid_bind = deepcopy(bind); invalid_bind["snapshot"] = transient
        self.assertTrue(stale.observe_record(invalid_bind)["failures"])
        self.assertEqual(meter.observe_record(bind)["failures"], [])
        self.assertEqual(meter.setup_index, 4)

    def test_exact_scoped_ground_roof_canopy_births_and_heights(self):
        for kind,canopy in ((BEHIND,False),(RAISED,False),(UNDERGROUND,False)):
            with self.subTest(kind=kind,canopy=canopy):
                outcome=check(kind,fixture(kind,canopy=canopy))
                self.assertEqual(len(outcome["landings"]),1)
                self.assertTrue(outcome["landings"][0]["landing"]["passed"])

    def test_canopy_alone_cannot_replace_required_native_roof_witness(self):
        with self.assertRaisesRegex(ValueError,"no required natural Goldenrod birth"):
            check(RAISED,fixture(RAISED,canopy=True))
        # A plausible raised tile outside the fixed production window cannot
        # replace one of the independently surveyed roof supports.
        with self.assertRaisesRegex(ValueError,"independent native roof tile/height window"):
            check(RAISED,fixture(RAISED,target=(370,327)))
        data=fixture(RAISED)
        data[2][-1]["data"]["initialLandingHeight"]["surfaceQuery"]["hit"]["height"] += 16
        with self.assertRaisesRegex(ValueError,"independent native roof tile/height window"):
            check(RAISED,data)

    def test_independent_roof_window_rejects_missing_and_invented_surfaces(self):
        from tools.overworld.devtools_goldenrod_spawn_measurement import check_roof_window
        catalog=json.loads((ROOT/"data/generated/overworld_wild_roof_catalog.json").read_text())
        check_roof_window(catalog)
        # Dropping one required model and inventing a Canopy each fail without
        # any game data being used to set the expectation.
        broken=deepcopy(catalog)
        broken["instances"]=[r for r in broken["instances"] if "model86" not in r["source"]]
        with self.assertRaisesRegex(ValueError,"independent 107-Roof/zero-Canopy window"):
            check_roof_window(broken)
        broken=deepcopy(catalog)
        row=next(r for r in broken["instances"] if "model86" in r["source"])
        row["surface_type"]="canopy"
        with self.assertRaisesRegex(ValueError,"independent 107-Roof/zero-Canopy window"):
            check_roof_window(broken)

    def test_all_copied_map_mask_target_height_faults_reach_own_predicate(self):
        for kind in CASES:
            for fault in ("goldenrod-wrong-map","goldenrod-wrong-mask","goldenrod-wrong-target","goldenrod-wrong-height"):
                with self.subTest(kind=kind,fault=fault):
                    report,samples,events,source=fixture(kind)
                    control=GoldenrodSpawnNegative(kind,fault)
                    mutated=control.mutate(dict(phase="observe",events=events),{})
                    self.assertTrue(control.applied)
                    with self.assertRaises(ValueError) as error:
                        witnesses(kind,report,samples,mutated["events"],source)
                    result=dict(passed=False,failures=[str(error.exception)])
                    validate_negative_result(kind,result,fault)

    def test_copied_profile_fault_preserves_pair_across_chunks(self):
        _,_,events,_=fixture(BEHIND)
        control=GoldenrodSpawnNegative(BEHIND,"goldenrod-wrong-map")
        first=control.mutate(dict(phase="observe",events=events[:1]),{})
        second=control.mutate(dict(phase="observe",events=events[1:]),{})
        self.assertEqual(first["events"][0]["data"]["resolverReceipts"],
                         second["events"][0]["data"]["finalization"]["receipt"]["resolverReceipts"])

    def test_underground_void_rejects_even_when_valid_birth_is_also_present(self):
        report,samples,events,source=fixture(UNDERGROUND)
        bad_report,bad_samples,bad_events,_=fixture(UNDERGROUND,target=(11,19))
        bad_report["naturalAttempts"][0]["spawnAttemptId"] = 2
        for final in (bad_events[0]["data"], bad_events[-1]["data"]["finalization"]["receipt"]):
            final.update(spawnAttemptId=2, finalizationId=8)
            final["resolverReceipts"][0]["finalizationId"] = 8
        bad_events[-1]["data"]["sequence"]=99
        bad_report["naturalAttempts"][0]["creations"][0]["sequence"]=99
        report["naturalAttempts"].extend(bad_report["naturalAttempts"])
        with self.assertRaisesRegex(ValueError,"outside the declared public corridor floor"):
            witnesses(UNDERGROUND,report,samples+bad_samples,events+bad_events,source)

    def test_wrong_behind_topology_and_raised_height_source_reject(self):
        data=fixture(BEHIND)
        data[-1]["behindTopology"][0]["landDataId"]+=1
        with self.assertRaisesRegex(ValueError,"north-of-roof topology"):check(BEHIND,data)
        for canopy in (False,):
            data=fixture(RAISED,canopy=canopy)
            data[2][-1]["data"]["initialLandingHeight"]["heightSource"]="native-refresh"
            with self.assertRaisesRegex(ValueError,"native height refresh did not succeed"):check(RAISED,data)

    def test_recipe_and_current_source_are_bound_without_actor_setup(self):
        for kind,case in CASES.items():
            raw=json.loads((ROOT/f"tests/overworld/test-recipes/{case['test']}.json").read_text())
            recipe=validate_test(raw)
            meter=GoldenrodSpawnMeasurement(recipe,source_inputs(ROOT))
            self.assertFalse(meter.result()["passed"])
            raw["setup"][0]["args"]["x"]+=1
            with self.assertRaisesRegex(ValueError,"declared setup or neutral window"):validate_test(raw)

    def test_controller_registration_reaches_exact_runtime_guard_for_all_three_cases(self):
        from tools.overworld import control
        from tools.overworld.proof_adapters import get_adapter
        for kind, case in CASES.items():
            with self.subTest(scenario=case["test"]):
                test = json.loads((ROOT / "tests/overworld/test-recipes" / (case["test"] + ".json")).read_text())
                registration, digest = control._shared_test_registration(test, ROOT)
                self.assertEqual(registration["evaluator"], kind)
                self.assertEqual(registration["recipeSha256"], digest)
                self.assertEqual(registration["requirements"], [case["requirement"]])
                # A changed runtime adapter must fail the real controller's
                # exact guard, not merely static scenario validation.
                adapter = get_adapter(kind)
                with patch.object(control, "get_adapter", return_value=replace(adapter, proof_level="S4")):
                    with self.assertRaisesRegex(ValueError, "exact measurement or reader contract"):
                        control._shared_test_registration(test, ROOT)
                with patch.object(control, "file_record", return_value={"sha256": "00" * 32}):
                    with self.assertRaises(ValueError):
                        control._shared_test_registration(test, ROOT)

    def test_old_water_ground_checker_remains_strict(self):
        spawn,sample=water_fixture()
        self.assertTrue(check_natural_water_surface(spawn,sample,species=165)["passed"])
        spawn["initialLandingHeight"]["surfaceQuery"].update(returnValue=1,hit=dict(height=1,surfaceType=0))
        with self.assertRaisesRegex(ValueError,"unknown or authored surface"):
            check_natural_water_surface(spawn,sample,species=165)


if __name__ == "__main__":unittest.main()
