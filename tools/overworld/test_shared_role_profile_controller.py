"""Controller integration with fake package/synthetic endpoints, not live proof."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from tools.overworld import control
from tools.overworld import test_devtools_test_proof as fixtures
from tools.overworld import test_devtools_role_profile_proof as role_fixtures
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_test_contract import validate_test


class SharedRoleProfileControllerTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.SharedProofTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        real = Path(__file__).resolve().parents[2]
        name = "profile.follower-mounted-owner-transfer"
        self.test = validate_test(json.loads((real / "tests/overworld/test-recipes" / (name + ".json")).read_text()))
        source = self.f.root / "tests/overworld/test-recipes" / (name + ".json")
        source.write_text(json.dumps(self.test))
        registry = json.loads((real / "tools/overworld/runtime_proof_registry.json").read_text())
        self.registration = registry["sharedTests"][name]
        self.registration["recipeSha256"] = fixtures.sha(source)
        (self.f.root / "tools/overworld/runtime_proof_registry.json").write_text(json.dumps(registry))
        events, initial, mounted = role_fixtures.RoleProfileProofTests().fixture()
        def enrich(value):
            result = self.f.current(value["frame"])
            actor = {**result["actors"][0], **deepcopy(value["actors"][0])}
            actor["sourceIdentity"] = deepcopy(events[0]["data"]["ownerBefore"]["sourceIdentity"])
            actor["engineIdentity"].update(current_map_id=value["context"]["mapId"], manager_index=7)
            result.update(deepcopy(value), prepared=True)
            result["actors"] = [actor]
            return result
        initial, mounted = enrich(initial), enrich(mounted)
        boot = deepcopy(initial)
        boot["frame"] -= 2; boot["nativeCycle"] -= 2
        boot["actors"] = []
        boot["selector"]["activeFollowerPartySlot"] = 0xFF
        boot["party"][2].update(species=56, form=0, level=3, hp=20, status=0)
        party_snapshot = deepcopy(initial)
        party_snapshot["frame"] -= 1; party_snapshot["nativeCycle"] -= 1
        party_snapshot["actors"] = []
        party_snapshot["selector"]["activeFollowerPartySlot"] = 0xFF
        final = deepcopy(mounted)
        final["frame"] += 1; final["nativeCycle"] += 1
        def setup_boundary(snapshot):
            return dict(eventsDrained=True, traceSequences={}, frame=snapshot["frame"],
                        nativeCycle=snapshot["nativeCycle"])
        party_receipt = dict(snapshot=deepcopy(party_snapshot), preparedOnly=True,
            value=dict(slot=2, action="replace", memoryPreflights=[]),
            party=deepcopy(party_snapshot["party"]), personality=2920357538, events=[],
            setupBoundary=setup_boundary(party_snapshot))
        follower_receipt = dict(snapshot=deepcopy(initial), preparedOnly=True,
            lifecycle="prepared-native-follower-lifecycle",
            requestedSubject=dict(slot=2, role="FOLLOWER", species=234, personality=2920357538,
                                  form=0, level=5), events=[], setupBoundary=setup_boundary(initial))
        receipt = dict(snapshot=deepcopy(mounted), preparedOnly=True, profileDiagnostics="owner-transfer",
            lifecycle="prepared-native-follower-lifecycle", events=deepcopy(events),
            profileObservation=dict(acceptedProof=False, events=deepcopy(events)),
            setupBoundary=setup_boundary(mounted))
        self.rows = [dict(phase="setup", initialSnapshot=boot),
            dict(phase="setup", action="prepare-sprint-stantler", command="party",
                 receipt=party_receipt, snapshot=party_snapshot),
            dict(phase="setup", action="prepare-sprint-follower", command="spawn",
                 receipt=follower_receipt, snapshot=initial),
            dict(phase="setup", action="mount-current-follower", command="spawn", receipt=receipt, snapshot=mounted),
            dict(phase="setup", action="bind-mount", command="bind", snapshot=deepcopy(mounted),
                 receipt=select_current_actor(mounted, mounted["actors"][0])),
            dict(phase="observe", boundarySnapshot=deepcopy(mounted)),
            dict(phase="observe", action="observe-owner", samples=[final], events=[], requestedGameFrames=1,
                 completedGameFrames=1, observedFieldFrames=1, nativeCycles=1,
                 cycleIntervals=[dict(cpuNs=100000,wallNs=100000,completedGameFrame=final["frame"])])]
        self.record = deepcopy(self.f.record)
        self.record.update(test=name, testSourceSha256=fixtures.sha(source),
                           sessionCleanup=dict(sessionId="session-proof",closed=True,errors=[]))
        self.record["fixtureProof"].update(registration=self.registration, testSourceSha256=fixtures.sha(source))
        self.refresh()
        self.install_control(real, registry)

    def install_control(self, real, registry):
        name = "profile.owner-reader-control"
        self.control_test = validate_test(json.loads((real / "tests/overworld/test-recipes" / (name + ".json")).read_text()))
        source = self.f.root / "tests/overworld/test-recipes" / (name + ".json")
        source.write_text(json.dumps(self.control_test))
        registration = registry["sharedTests"][name]
        registration["recipeSha256"] = fixtures.sha(source)
        (self.f.root / "tools/overworld/runtime_proof_registry.json").write_text(json.dumps(registry))
        self.control_rows = deepcopy(self.rows)
        self.control_rows.pop(5)  # Control recording starts before prepared setup.
        events, _, _ = role_fixtures.RoleProfileProofTests().calibrated_fixture()
        receipt = self.control_rows[3]["receipt"]
        receipt.update(profileDiagnostics="owner-transfer-control", events=deepcopy(events))
        receipt["profileObservation"]["events"] = deepcopy(events)
        directory = self.f.root / "build/overworld-devtools/test-owner-control"
        directory.mkdir()
        self.control_observations = directory / "observations.jsonl"
        self.control_manifest = directory / "manifest.json"
        self.control_record = deepcopy(self.record)
        self.control_record.update(test=name, runId="test-owner-control", sessionId="session-owner-control",
            testSourceSha256=fixtures.sha(source),
            sessionCleanup=dict(sessionId="session-owner-control",closed=True,errors=[]))
        self.control_record["identity"]["sessionId"] = "session-owner-control"
        self.control_record["fixtureProof"].update(registration=registration,testSourceSha256=fixtures.sha(source))
        self.write_control()
        with patch.object(control,"source_record",return_value={"hash":"source"}):
            accepted = control.finalize_shared_test(self.control_test,self.control_record,self.f.root)
        self.assertTrue(accepted["acceptedProof"],accepted)
        self.control_record.update(accepted)
        self.write_control_manifest()

    def write_control(self):
        self.control_observations.write_text("".join(json.dumps(row)+"\n" for row in self.control_rows))
        self.control_record["observationsArtifact"] = dict(path=str(self.control_observations),
            size=self.control_observations.stat().st_size,sha256=fixtures.sha(self.control_observations))
        self.control_record["evaluation"] = control._replay_shared_test(self.control_test,self.control_rows,repo=self.f.root)

    def write_control_manifest(self):
        self.control_manifest.write_text(json.dumps(self.control_record))
        artifact = dict(path=str(self.control_manifest),size=self.control_manifest.stat().st_size,
                        sha256=fixtures.sha(self.control_manifest))
        self.record["recorderControlArtifact"] = artifact
        self.record["fixtureProof"]["recorderControlArtifact"] = deepcopy(artifact)

    def refresh(self):
        self.f.rows = self.rows; self.f.write_rows()
        self.record["observationsArtifact"] = self.f.artifact()
        self.record["evaluation"] = control._replay_shared_test(self.test,self.rows,repo=self.f.root)

    def finish(self):
        with patch.object(control,"source_record",return_value={"hash":"source"}):
            return control.finalize_shared_test(self.test,self.record,self.f.root)

    def test_exact_seven_row_transfer_accepts_only_narrow_claim(self):
        self.assertTrue(self.record["evaluation"]["passed"], self.record["evaluation"])
        result=self.finish()
        self.assertTrue(result["acceptedProof"],result)
        proof=result["proofAcceptance"]
        self.assertEqual(proof["claims"],["live-actor-identity","profile-resolution"])
        self.assertEqual(proof["observedFrames"],1)
        self.assertEqual(len(proof["measurements"]),3)
        self.assertEqual(len(proof["transferControls"]["controls"]),8)
        self.assertTrue(proof["recorderControl"]["revalidated"])
        self.assertEqual(proof["recorderControl"]["runId"],"test-owner-control")

    def test_missing_stale_and_mutated_independent_control_are_rejected(self):
        for fault in ("missing", "source", "rom", "session", "cleanup", "native-bytes", "unaccepted"):
            with self.subTest(fault=fault):
                original = deepcopy((self.record,self.control_record,self.control_rows))
                if fault=="missing":
                    self.record.pop("recorderControlArtifact")
                    self.record["fixtureProof"].pop("recorderControlArtifact")
                else:
                    if fault=="source":self.control_record["fixtureProof"]["source"]={"hash":"old"}
                    if fault=="rom":self.control_record["identity"]["rom"]["sha256"]="0"*64
                    if fault=="session":self.control_record["sessionId"]=self.record["sessionId"]
                    if fault=="cleanup":self.control_record["sessionCleanup"]["closed"]=False
                    if fault=="unaccepted":self.control_record["acceptedProof"]=False
                    if fault=="native-bytes":
                        receipt=self.control_rows[3]["receipt"]
                        data=receipt["profileObservation"]["events"][-1]["data"]
                        data["ownerHex"]="ff"+data["ownerHex"][2:]
                        receipt["events"]=deepcopy(receipt["profileObservation"]["events"])
                        self.write_control()
                        self.assertTrue(self.control_record["evaluation"]["passed"])
                    self.write_control_manifest()
                self.assertFalse(self.finish()["acceptedProof"])
                self.record,self.control_record,self.control_rows=original
                self.write_control()
                self.write_control_manifest()

    def test_changed_profile_fails_even_when_generic_identity_replay_passes(self):
        for mirror in (False, True):
            with self.subTest(mirrored_stream=mirror):
                original=deepcopy(self.rows)
                data=self.rows[3]["receipt"]["profileObservation"]["events"][1]["data"]
                data["profileHex"]="ff"+data["profileHex"][2:]
                if mirror:
                    self.rows[3]["receipt"]["events"]=deepcopy(self.rows[3]["receipt"]["profileObservation"]["events"])
                self.refresh()
                self.assertTrue(self.record["evaluation"]["passed"])
                self.assertFalse(self.finish()["acceptedProof"])
                self.rows=original

    def test_recording_boundary_must_keep_current_identity_and_clock(self):
        for fault in ("missing", "clock", "identity", "phase", "field"):
            with self.subTest(fault=fault):
                original=deepcopy(self.rows)
                boundary=self.rows[5]["boundarySnapshot"]
                if fault=="missing":self.rows.pop(5)
                elif fault=="clock":boundary["nativeCycle"]-=1
                elif fault=="identity":boundary["actors"][0]["identityVerified"]=False
                elif fault=="phase":self.rows[5]["phase"]="setup"
                else:boundary["fieldAvailable"]=False
                with self.assertRaises((ValueError, control.ValidationFailure)):
                    control._shared_role_transfer(self.rows,self.record)
                self.rows=original

    def test_endpoint_uses_recording_boundary_not_bind_clock(self):
        for key in ("frame", "nativeCycle"):
            self.rows[5]["boundarySnapshot"][key]+=2
            self.rows[6]["samples"][0][key]+=2
        self.rows[6]["cycleIntervals"][0]["completedGameFrame"]+=2
        self.refresh()
        result=self.finish()
        self.assertTrue(result["acceptedProof"],result)

    def test_missing_cleanup_and_stale_inputs_cannot_pass(self):
        for fault in ("cleanup", "source", "rom"):
            with self.subTest(fault=fault):
                old=deepcopy(self.record)
                if fault=="cleanup":self.record.pop("sessionCleanup")
                if fault=="source":self.record["fixtureProof"]["source"]={"hash":"old"}
                if fault=="rom":self.record["identity"]["rom"]["sha256"]="0"*64
                self.assertFalse(self.finish()["acceptedProof"])
                self.record=old

    def test_wrong_action_and_extra_setup_are_rejected(self):
        for fault in ("action", "extra-setup"):
            with self.subTest(fault=fault):
                original=deepcopy(self.rows)
                if fault=="action":self.rows[1]["action"]="unlisted"
                else:self.rows.insert(1,deepcopy(self.rows[0]))
                self.refresh()
                self.assertFalse(self.finish()["acceptedProof"])
                self.rows=original


if __name__ == "__main__": unittest.main()
