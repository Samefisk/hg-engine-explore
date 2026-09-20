"""Pure host data tests; no emulator, ROM proof, or validator replacement."""
from pathlib import Path
import json
import tempfile
import unittest
from copy import deepcopy

from tools.overworld.devtools_records import (
    Recording, load_recipe, recording_to_draft, save_recipe,
    select_current_actor, validate_recipe,
    engine_binding_identity,
)


class EngineBindingTests(unittest.TestCase):
    def identity(self):
        return {"pointer": 0x02001000, "manager_index": 10,
                "id_lookup": {"first_active_pointer": 0x02001000,
                    "matching_objects": [{"pointer": 0x02001000, "flags": 1066017,
                        "active": True, "flag25": False, "lookup_eligible": True}]}}

    def test_motion_flags_change_without_changing_binding(self):
        before = self.identity()
        after = deepcopy(before)
        after["id_lookup"]["matching_objects"][0]["flags"] = 1065987
        retained = deepcopy(after)
        self.assertEqual(engine_binding_identity(before), engine_binding_identity(after))
        self.assertEqual(after, retained)

    def test_identity_bits_lookup_and_pointers_still_matter(self):
        before = self.identity()
        for kind in ("inactive", "flag25", "pointer", "lookup", "row-count"):
            after = deepcopy(before)
            row = after["id_lookup"]["matching_objects"][0]
            if kind == "inactive": row.update(flags=0, active=False, lookup_eligible=False)
            elif kind == "flag25": row.update(flags=0x02000001, flag25=True, lookup_eligible=False)
            elif kind == "pointer": after["pointer"] += 4
            elif kind == "lookup": after["id_lookup"]["first_active_pointer"] += 4
            else: after["id_lookup"]["matching_objects"].append(deepcopy(row))
            with self.subTest(kind=kind):
                self.assertNotEqual(engine_binding_identity(before), engine_binding_identity(after))

    def test_bad_flags_and_inconsistent_membership_reject(self):
        for flags in (None, True, -1, 0x100000000, 0, 0x02000001):
            value = self.identity()
            value["id_lookup"]["matching_objects"][0]["flags"] = flags
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                engine_binding_identity(value)


def actor(**changes):
    result = {
        "handle": {"value": 131072, "slot": 0, "generation": 2, "fieldEpoch": 4,
                   "mapGeneration": 5, "encounterGeneration": 6},
        "subjectIdentity": 789, "species": 165, "role": "WILD", "active": True,
        "presentationAttached": True, "identityVerified": True,
        "authorityGeneration": 2, "engineAnchorGeneration": 2, "presentationGeneration": 2,
        "engineIdentity": {"pointer": 0x02202000, "in_manager": True},
        "logical": {"x": 553, "y": 390}, "render": {"x": 553, "y": 390},
        "motionPhase": "IDLE", "motionKind": "NONE",
    }
    result.update(changes)
    return result


def snapshot(frame=1, actors=None):
    return {"frame": frame, "actors": [actor()] if actors is None else actors,
            "context": {"fieldEpoch": 4, "mapGeneration": 5, "mapId": 34},
            "player": {}, "party": [], "terrain": {}}


def identity():
    return {"sessionId": "diagnostic-1", "startedAt": "2026-09-05T18:00:00Z",
            "rom": {"sha256": "a" * 64}, "save": {"sha256": "b" * 64},
            "debugDescriptor": {"sha256": "c" * 64}}


def large_snapshot(frame=1):
    """Structured host-only observations, not captured game or ROM data."""
    sample = snapshot(frame)
    sample["terrain"] = {"cells": [
        {"x": x, "y": z, "z": z, "attribute": 0, "behavior": 0,
         "block": 0, "collision": False, "loaded": True, "matrix_index": 0,
         "terrain_class": 0, "provenance": {
             **{key: 0x02000000 for key in ("attributeAddress", "chunkPointer", "fieldPointer",
                 "landManagerPointer", "mapMatrixPointer", "readerPointer")},
             **{key: 0 for key in ("chunkMatrixIndex", "chunkModelLoaded", "currentMatrixIndex",
                 "currentSlot", "landDataId", "mapHeaderId", "matrixAltitude", "matrixHeight",
                 "matrixId", "matrixWidth", "rawWord", "selectedSlot")},
             "landDataIdentity": "current-map-matrix", "store": "rolling-land-manager",
             "terrainAttributesPointer": None}}
        for x in range(15) for z in range(15)]}
    sample["nativeObservation"] = {"resolvedProfiles": [
        {"fingerprint": profile, "lanes": ["00" * 72] * 2,
         "requestHex": "00" * 44, "resultHex": "00" * 200,
         "sourceSha256": "a" * 64, "appliedOverrides": 0, "resolved": True}
        for profile in range(6)]}
    return sample


def recipe(op="step", args=None, mode="normal"):
    return {"schemaVersion": 1, "mode": mode, "actions": [{"op": op, "args": {} if args is None else args}]}


class RecordingTests(unittest.TestCase):
    def test_full_tool_identity_survives_export_and_draft(self):
        source = identity()
        source['toolInputs'] = {f'tools/overworld/devtools_fixture_{i}.py': 'a' * 64 for i in range(250)}
        self.assertGreater(len(json.dumps(source).encode()), 16384)
        record = Recording().export(source, 'prepared')
        self.assertEqual(record['identity'], source)
        draft = recording_to_draft(record, 'large-identity', 'Retain all source hashes.')
        self.assertEqual(draft['origin']['identity'], source)

    def test_record_identity_remains_bounded_on_both_paths(self):
        from tools.overworld.devtools_records import MAX_IDENTITY_BYTES
        source = {**identity(), 'tooLarge': 'x' * MAX_IDENTITY_BYTES}
        with self.assertRaisesRegex(ValueError, 'JSON record exceeds'):
            Recording().export(source, 'prepared')
        record = Recording().export(identity(), 'prepared')
        record['identity'] = source
        with self.assertRaisesRegex(ValueError, 'JSON record exceeds'):
            recording_to_draft(record, 'large-identity', 'Retain all source hashes.')

    def test_large_native_snapshot_survives_recordable_path(self):
        from tools.overworld.devtools import _recordable_snapshot
        sample = large_snapshot()
        self.assertGreater(len(json.dumps(sample).encode()), 65536)
        sample["samples"] = [large_snapshot(2)]
        sample["events"] = [{"kind": "trace"}]
        sample["screenshot"] = {"url": "x" * 200000, "frame": 1}
        recorder = Recording()
        recorder.add_snapshot(1, _recordable_snapshot(sample))
        saved = recorder.export(identity(), "normal")["snapshots"][0]
        self.assertEqual(saved["nativeObservation"], sample["nativeObservation"])
        self.assertEqual(saved["terrain"], sample["terrain"])
        self.assertEqual(saved["actors"], sample["actors"])
        self.assertNotIn("samples", saved)
        self.assertNotIn("events", saved)
        self.assertEqual(saved["screenshot"], {"frame": 1})

    def test_snapshot_bytes_bound_eviction_and_same_frame_replacement(self):
        sample = large_snapshot()
        size = len(json.dumps(sample, separators=(",", ":"), ensure_ascii=False).encode())
        recorder = Recording(max_frames=10, max_bytes=size * 2)
        for frame in (1, 2, 2, 3):
            recorder.add_snapshot(frame, large_snapshot(frame))
        result = recorder.export(identity(), "normal")
        self.assertEqual([s["frame"] for s in result["snapshots"]], [2, 3])
        self.assertEqual(result["counts"]["snapshotsDropped"], 1)
        self.assertEqual(result["counts"]["snapshotsReplaced"], 1)
        self.assertEqual(result["counts"]["snapshotBytesRetained"], size * 2)
        self.assertEqual(result["limits"]["maxSnapshotBytesTotal"], size * 2)
        self.assertTrue(result["truncated"])

    def test_oversized_snapshot_rejected_without_losing_prior_rows(self):
        recorder = Recording()
        recorder.add_snapshot(1, snapshot())
        with self.assertRaisesRegex(ValueError, "exceeds 1048576 bytes"):
            recorder.add_snapshot(2, {**snapshot(2), "extra": "x" * 1048576})
        self.assertEqual(recorder.export(identity(), "normal")["counts"]["snapshotsReceived"], 1)

    def test_larger_replacement_evicts_old_rows_and_counts_utf8_bytes(self):
        small = snapshot()
        big = {**snapshot(2), "note": "ø" * 1000}
        size = len(json.dumps(big, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
        recorder = Recording(max_bytes=size)
        recorder.add_snapshot(1, small)
        recorder.add_snapshot(2, snapshot(2))
        recorder.add_snapshot(2, big)
        result = recorder.export(identity(), "normal")
        self.assertEqual(result["snapshots"], [big])
        self.assertEqual(result["counts"]["snapshotsDropped"], 1)
        self.assertEqual(result["counts"]["snapshotsReplaced"], 1)
        self.assertEqual(result["counts"]["snapshotBytesRetained"], size)
        with self.assertRaisesRegex(ValueError, "JSON record exceeds"):
            recorder.add_snapshot(3, {**big, "frame": 3, "extra": True})
        self.assertEqual(recorder.export(identity(), "normal")["snapshots"], [big])

    def test_bounded_ring_counts_and_latest_terminal_state(self):
        recorder = Recording(max_frames=2, max_events=2)
        for frame in range(4):
            recorder.add_snapshot(frame, snapshot(frame))
            recorder.add_event(frame, "note", {"message": str(frame)})
        result = recorder.export(identity(), "normal")
        self.assertEqual([s["frame"] for s in result["snapshots"]], [2, 3])
        self.assertEqual([e["frame"] for e in result["events"]], [2, 3])
        self.assertEqual(result["counts"]["snapshotsDropped"], 2)
        self.assertEqual(result["counts"]["eventsDropped"], 2)
        self.assertTrue(result["truncated"])
        self.assertFalse(result["acceptedProof"])
        self.assertNotIn("passed", result)

    def test_duplicate_frame_is_explicitly_replaced(self):
        recorder = Recording()
        recorder.add_snapshot(1, snapshot())
        recorder.add_snapshot(1, snapshot(1, []))
        result = recorder.export(identity(), "normal")
        self.assertEqual(result["counts"]["snapshotsReceived"], 2)
        self.assertEqual(result["counts"]["snapshotsReplaced"], 1)
        self.assertEqual(result["snapshots"][0]["actors"], [])

    def test_recording_owns_data_and_export_is_detached(self):
        recorder = Recording()
        sample = snapshot()
        recorder.add_snapshot(1, sample)
        sample["actors"][0]["species"] = 1
        result = recorder.export(identity(), "normal")
        result["snapshots"][0]["actors"][0]["species"] = 2
        self.assertEqual(recorder.export(identity(), "normal")["snapshots"][0]["actors"][0]["species"], 165)

    def test_no_heuristic_stall_or_render_distance_failure(self):
        recorder = Recording()
        for frame in range(60):
            sample = snapshot(frame)
            sample["actors"][0]["render"] = {"x": 554, "y": 390}
            recorder.add_snapshot(frame, sample)
        self.assertEqual(recorder.export(identity(), "normal")["definiteFailures"], [])

    def test_failed_preparation_taints_even_after_event_is_dropped(self):
        recorder = Recording(max_events=1)
        recorder.add_event(1, "command", {"op": "spawn", "args": {"species": 165}, "ok": False})
        recorder.add_event(2, "note", {"message": "later"})
        self.assertEqual(recorder.export(identity(), "normal")["mode"], "prepared")

    def test_detects_duplicate_and_changed_subject_not_new_generation(self):
        recorder = Recording()
        recorder.add_snapshot(1, snapshot(1, [actor(), actor()]))
        recorder.add_snapshot(2, snapshot(2, [actor(subjectIdentity=790)]))
        fresh = actor(subjectIdentity=791)
        fresh["handle"]["generation"] = 3
        fresh["handle"]["value"] = 3 << 16
        recorder.add_snapshot(3, snapshot(3, [fresh]))
        codes = [f["code"] for f in recorder.export(identity(), "normal")["definiteFailures"]]
        self.assertEqual(codes, ["duplicate-active-actor", "subject-changed-without-new-handle"])

    def test_invalid_handle_context_and_position_are_definite(self):
        recorder = Recording()
        broken = actor(logical={"x": 40000, "y": 0})
        broken["handle"]["fieldEpoch"] = 3
        recorder.add_snapshot(1, snapshot(1, [broken]))
        broken["handle"]["value"] = 5
        recorder.add_snapshot(2, snapshot(2, [broken]))
        codes = {f["code"] for f in recorder.export(identity(), "normal")["definiteFailures"]}
        self.assertEqual(codes, {"stale-active-context", "invalid-public-position", "invalid-active-identity"})

    def test_role_rebound_and_suspended_transition_are_not_false_failures(self):
        recorder = Recording()
        follower = actor(role="FOLLOWER")
        recorder.add_snapshot(1, snapshot(1, [follower]))
        mounted = actor(role="MOUNTED", authorityGeneration=3, engineAnchorGeneration=3)
        recorder.add_snapshot(2, snapshot(2, [mounted]))
        suspended = actor(role="MOUNTED", identityVerified=False, motionPhase="SUSPENDED")
        suspended["handle"]["fieldEpoch"] = 3
        recorder.add_snapshot(3, snapshot(3, [suspended]))
        self.assertFalse(recorder.failure_summary()["hasDefiniteFailures"])
        self.assertEqual(recorder.export(identity(), "normal")["subjects"], [])

    def test_failure_ring_is_bounded(self):
        recorder = Recording(max_events=1)
        for frame in range(3):
            recorder.add_snapshot(frame, snapshot(frame, [actor(logical={"x": True, "y": 1})]))
        result = recorder.export(identity(), "normal")
        self.assertEqual(len(result["definiteFailures"]), 1)
        self.assertEqual(result["counts"]["failuresDropped"], 2)
        summary = recorder.failure_summary()
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["retained"], 1)
        self.assertEqual(summary["dropped"], 2)
        self.assertTrue(summary["hasDefiniteFailures"])
        self.assertEqual(summary["latest"][0]["frame"], 2)

    def test_summary_has_no_stall_guess_and_owns_its_values(self):
        recorder = Recording()
        recorder.add_snapshot(1, snapshot())
        self.assertFalse(recorder.failure_summary()["hasDefiniteFailures"])
        recorder.add_snapshot(2, snapshot(2, [actor(render={"x": 40000, "y": 1})]))
        summary = recorder.failure_summary()
        summary["latest"][0]["code"] = "changed"
        self.assertEqual(recorder.failure_summary()["latest"][0]["code"], "invalid-public-position")

    def test_bad_types_limits_and_nonfinite_data_fail(self):
        for limits in ({"max_frames": 0}, {"max_frames": True}, {"max_events": 4001},
                       {"max_bytes": 0}, {"max_bytes": True}, {"max_bytes": 1800 * 65536 + 1}):
            with self.subTest(limits=limits), self.assertRaises(ValueError):
                Recording(**limits)
        recorder = Recording()
        for frame, sample in [(True, snapshot()), (2, snapshot()), (1, snapshot(1, [{}] * 33)), (1, snapshot(True))]:
            with self.subTest(frame=frame), self.assertRaises(ValueError):
                recorder.add_snapshot(frame, sample)
        for data in ({"bad": float("nan")}, {"big": "x" * 9000}, {"bad": object()}):
            with self.subTest(data=str(data)[:30]), self.assertRaises(ValueError):
                recorder.add_event(1, "note", data)


class CurrentSubjectTests(unittest.TestCase):
    def test_full_live_identity_is_selected_and_exported(self):
        selected = select_current_actor(snapshot(), actor())
        self.assertEqual(selected["handle"], actor()["handle"])
        self.assertEqual(selected["observedFrame"], 1)
        self.assertTrue(selected["identityVerified"])
        recorder = Recording()
        recorder.add_snapshot(1, snapshot())
        self.assertEqual(recorder.export(identity(), "normal")["subjects"], [selected])

    def test_species_or_slot_only_selection_cannot_pass(self):
        for subject in ({"species": 165}, {"slot": 0}, {"handle": actor()["handle"]}):
            with self.subTest(subject=subject), self.assertRaises(ValueError):
                select_current_actor(snapshot(), subject)

    def test_all_generation_and_subject_changes_reject_stale_selection(self):
        for field in ("fieldEpoch", "mapGeneration", "encounterGeneration", "generation"):
            sample = snapshot()
            sample["actors"][0]["handle"][field] += 1
            with self.subTest(field=field), self.assertRaises(ValueError):
                select_current_actor(sample, actor())
        for field, value in (("subjectIdentity", 790), ("species", 166), ("role", "MOUNTED"),
                             ("authorityGeneration", 3), ("engineAnchorGeneration", 3), ("presentationGeneration", 3)):
            with self.subTest(field=field), self.assertRaises(ValueError):
                select_current_actor(snapshot(1, [actor(**{field: value})]), actor())

    def test_lifecycle_and_world_evidence_are_required(self):
        for changes in ({"active": False}, {"presentationAttached": False}, {"identityVerified": False},
                        {"authorityGeneration": 0}, {"engineAnchorGeneration": 0}, {"presentationGeneration": 0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                select_current_actor(snapshot(1, [actor(**changes)]), actor())
        for sample in (snapshot(1, []), snapshot(1, [actor(), actor()]), {"frame": 1, "actors": [actor()]},
                       {**snapshot(), "context": {"fieldEpoch": 3, "mapGeneration": 5}}):
            with self.subTest(sample=sample), self.assertRaises(ValueError):
                select_current_actor(sample, actor())


class RecipeTests(unittest.TestCase):
    def test_uses_actual_service_defaults_and_prepared_arguments(self):
        self.assertEqual(validate_recipe(recipe())["actions"][0], {"op": "step", "args": {"frames": 1, "keys": []}})
        for op, args in (("teleport", {"map": 34, "x": 550, "z": 381}),
                         ("spawn", {"species": 165}), ("party", {"slot": 0, "hp": 1})):
            with self.subTest(op=op):
                self.assertEqual(validate_recipe(recipe(op, args, "prepared"))["actions"][0]["op"], op)
                with self.assertRaises(ValueError):
                    validate_recipe(recipe(op, args))

    def test_unknown_operations_fields_ranges_and_coercions_rejected(self):
        invalid = [recipe("memory.write"), recipe("script"), recipe("reset"), recipe("step", {"frames": 601}),
                   recipe("step", {"frames": True}), recipe("step", {"keys": ["UP", "DOWN"]}),
                   recipe("step", {"address": 123}), recipe("spawn", {"species": 0}, "prepared"),
                   recipe("party", {"slot": 6, "hp": 1}, "prepared"), recipe("party", {"slot": 0}, "prepared"),
                   {**recipe(), "acceptedProof": True}, {**recipe(), "schemaVersion": True},
                   {**recipe(), "actions": []}, {**recipe(), "actions": recipe()["actions"] * 257},
                   {**recipe(), "actions": [{"op": [], "args": {}}]},
                   {**recipe(), "actions": [{"op": "step", "args": None}]}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_recipe(value)

    def test_named_save_load_are_roundtrip_and_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = save_recipe(directory, "ledyba-route", recipe())
            self.assertEqual(path.name, "ledyba-route.json")
            self.assertEqual(load_recipe(directory, "ledyba-route"), validate_recipe(recipe()))
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                save_recipe(directory, "ledyba-route", recipe("step", {"frames": 2}))
            self.assertEqual(path.read_bytes(), before)

    def test_names_links_duplicate_keys_and_large_files_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in ("../outside", "/tmp/outside", "a/b", "a\\b", ".hidden", "a..b", "A", "a" * 65):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    save_recipe(directory, name, recipe())
                with self.assertRaises(ValueError):
                    load_recipe(directory, name)
            source = save_recipe(directory, "source", recipe())
            (Path(directory) / "link.json").symlink_to(source)
            with self.assertRaises(OSError):
                load_recipe(directory, "link")
            with self.assertRaises(FileExistsError):
                save_recipe(directory, "link", recipe())
            duplicate = Path(directory) / "duplicate.json"
            duplicate.write_text('{"schemaVersion":1,"schemaVersion":1}')
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_recipe(directory, "duplicate")
            (Path(directory) / "large.json").write_text(" " * 65537)
            with self.assertRaisesRegex(ValueError, "large"):
                load_recipe(directory, "large")


class DraftTests(unittest.TestCase):
    def recording(self):
        recorder = Recording()
        recorder.add_snapshot(1, snapshot())
        recorder.add_event(1, "command", {"op": "step", "args": {"frames": 8, "keys": ["UP"]}, "ok": True})
        return recorder.export(identity(), "normal")

    def test_draft_keeps_origin_and_commands_without_minting_acceptance(self):
        recorded = self.recording()
        draft = recording_to_draft(recorded, "ledyba-chain", {"source": "Authored chain contract", "observable": "Four complete skids"}, actor())
        self.assertEqual(draft["origin"]["identity"], identity())
        self.assertEqual(draft["recordedCommands"], recorded["events"])
        self.assertEqual(draft["status"], "planned")
        self.assertEqual(draft["verificationStatus"], "unverified")
        self.assertFalse(draft["acceptedProof"])
        self.assertNotIn("passed", draft)
        self.assertNotIn("proofEvidence", draft)
        self.assertEqual(draft["verification"]["setupAudit"], "pending")
        self.assertEqual(len(draft["blockers"]), 2)
        self.assertEqual(draft["subject"]["species"], 165)

    def test_unknown_expectation_identity_and_actor_stay_blocked(self):
        recorded = self.recording()
        recorded["identity"] = {}
        draft = recording_to_draft(recorded, "unknown", None)
        self.assertIsNone(draft["expectation"])
        self.assertIsNone(draft["subject"])
        self.assertTrue(any("independent source" in b for b in draft["blockers"]))
        self.assertTrue(any("observable" in b for b in draft["blockers"]))
        self.assertEqual(sum("SHA-256" in b for b in draft["blockers"]), 3)

    def test_failed_setup_remains_recorded_and_prepared(self):
        recorded = self.recording()
        recorded["events"].append({"frame": 2, "kind": "command", "data": {"op": "spawn", "args": {"species": 165}, "ok": False}})
        recorded["truncated"] = True
        draft = recording_to_draft(recorded, "retry", "Hop visibly", actor())
        self.assertEqual(draft["origin"]["mode"], "prepared")
        self.assertEqual(draft["verification"]["kind"], "controlled-case")
        self.assertEqual(len(draft["verification"]["setupMutations"]), 1)
        self.assertFalse(draft["recordedCommands"][-1]["data"]["ok"])
        self.assertTrue(any("failed" in b for b in draft["blockers"]))
        self.assertTrue(any("truncated" in b for b in draft["blockers"]))

    def test_stale_selection_and_invalid_action_never_become_executable_recipe(self):
        recorded = self.recording()
        recorded["snapshots"][-1]["actors"][0]["identityVerified"] = False
        recorded["events"][0]["data"]["args"] = {"frames": 9000}
        draft = recording_to_draft(recorded, "bad", "Expected motion", actor())
        self.assertIsNone(draft["subject"])
        self.assertIsNone(draft["proposedRecipe"])
        self.assertEqual(draft["recordedCommands"][0]["data"]["args"]["frames"], 9000)
        self.assertTrue(any("selection failed" in b for b in draft["blockers"]))

    def test_a_proof_receipt_is_not_a_recording(self):
        for value in ({"passed": True}, {"kind": "overworld-diagnostic-recording", "acceptedProof": True}):
            with self.assertRaises(ValueError):
                recording_to_draft(value, "bad", "Motion")


if __name__ == "__main__":
    unittest.main()
