"""Controller checks of real meter output; no fabricated classifier result."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from tempfile import TemporaryDirectory
from hashlib import sha256

from tools.overworld.route_control_proof import route_control_measurements
from tools.overworld import test_devtools_route_control_measurement as streams


ROOT = Path(__file__).resolve().parents[2]


def fixture():
    source = streams.LiveRouteControlTests()
    meter, chunk = source.chunk_case(4)
    meter.observe_record(chunk)
    closed = source.receipt(meter, "player-start-stall", "closed", requiresCoreClose=True)
    control = source.value(meter, "player-start-stall", meter.histories + [closed], "closed")
    control["closed"] = True
    meter.observe_cleanup(dict(closed=True, advancedFrames=0, released=True,
        frame=meter.latest["frame"], snapshot=deepcopy(meter.latest), routeControl=control))
    report = meter.finish()
    assert report["passed"] is True
    # The shared host stream uses a synthetic saved identity. Specialize only
    # that identity for this saved-fixture contract, not any checker outcome.
    def saved(value):
        if isinstance(value, list):
            return [saved(v) for v in value]
        if isinstance(value, dict):
            return {k: (2046726716 if k in ("personality", "subjectIdentity") else
                        6 if k == "level" else saved(v)) for k, v in value.items()}
        return value
    report = saved(report)
    return report, {"observerControlCleanup": deepcopy(report["cleanup"])}


class RouteControlProofTests(unittest.TestCase):
    def test_exact_registration_rejects_claim_role_and_measurement_drift(self):
        from tools.overworld.control import _shared_test_registration, ValidationFailure
        recipe = json.loads((ROOT / "tests/overworld/test-recipes/observation.live-route-control.json").read_text())
        registry = json.loads((ROOT / "tools/overworld/runtime_proof_registry.json").read_text())
        with TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "tests/overworld/test-recipes/observation.live-route-control.json"
            target.parent.mkdir(parents=True)
            registered = root / "tools/overworld/runtime_proof_registry.json"
            registered.parent.mkdir(parents=True)
            cases = (None, "role", "claim", "measurement", "dependency")
            for case in cases:
                with self.subTest(case=case):
                    test, table = deepcopy(recipe), deepcopy(registry)
                    entry = table["sharedTests"][test["id"]]
                    if case == "role": test["subjects"][0]["role"] = "MOUNTED"
                    if case == "claim": entry["claims"] = ["live-actor-identity"]
                    if case == "measurement": test["measurements"][0]["setupTransitions"] = [33]
                    if case == "dependency": entry["recorderControlRequirement"] = "legacy.live-observer-controls"
                    content = json.dumps(test).encode()
                    target.write_bytes(content)
                    entry["recipeSha256"] = sha256(content).hexdigest()
                    registered.write_text(json.dumps(table))
                    if case is None:
                        actual, _ = _shared_test_registration(test, root)
                        self.assertEqual(actual, entry)
                    else:
                        with self.assertRaises((ValidationFailure, ValueError)):
                            _shared_test_registration(test, root)

    def test_real_meter_output_has_original_registry_rows_and_is_not_mutated(self):
        report, manifest = fixture()
        before = deepcopy((report, manifest))
        rows = route_control_measurements(report, manifest)
        self.assertEqual([r["name"] for r in rows], ["live-route-recorder-baseline-identity",
                                                   "live-route-recorder-baseline-and-faults"])
        self.assertEqual([r["value"] for r in rows], [1, [1, 1, 1]])
        self.assertEqual((report, manifest), before)

    def test_required_evidence_controls(self):
        mutations = {
            "baseline-cpu": lambda m: m["baseline"]["cpuSamples"].__setitem__(0, 1000000000),
            "missing-cpu": lambda m: m["baseline"].pop("cpuSamples"),
            "short-cpu": lambda m: m["baseline"].__setitem__("cpuSamples", [1]*15),
            "wrong-subject": lambda m: m["subject"].__setitem__("subjectIdentity", 99),
            "wrong-slot": lambda m: m["baseline"]["preparedSetup"][1]["receipt"]["requestedSubject"].__setitem__("slot", 2),
            "unheld": lambda m: m["baseline"].__setitem__("heldFirstThree", False),
            "few-moves": lambda m: m["baseline"].__setitem__("playerMotions", 3),
            "no-actor": lambda m: m["baseline"]["settledSnapshot"].__setitem__("actors", []),
            "native-hp": lambda m: m["baseline"]["settledSnapshot"]["partyObservation"].__setitem__("nativeGetterChecks", []),
            "pending-motion": lambda m: m["baseline"]["settledSnapshot"]["actors"][0].__setitem__("motionPhase", "MOVING"),
            "fault-cycle": lambda m: m["detections"]["cpu-hitch"].__setitem__("nativeCycle", 1),
            "unrelated-hitch": lambda m: m["detections"]["cpu-hitch"]["cpuSamples"].__setitem__(0, 1000000000),
            "pin-coverage": lambda m: m["detections"]["player-start-stall"]["pins"].pop(),
            "pin-frame": lambda m: m["detections"]["player-start-stall"].__setitem__("admissionFrame", 0),
            "pin-value": lambda m: m["detections"]["player-start-stall"]["pins"][0]["after"].__setitem__(0, 99),
            "admission": lambda m: m["detections"]["player-start-stall"]["admission"]["admission"]["target"].__setitem__(0, 99),
            "cleanup-frame": lambda m: m["cleanup"].__setitem__("frame", 1),
            "cleanup-close": lambda m: m["cleanup"]["routeControl"].__setitem__("requiresCoreClose", False),
            "ordinary-failure": lambda m: m["failures"].append({"code": "ordinary-fault"}),
        }
        original, manifest = fixture()
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                report = deepcopy(original)
                mutate(report)
                with self.assertRaises(ValueError):
                    route_control_measurements(report, manifest)
        for key in ("start", "commit", "finish", "control"):
            with self.subTest(missing_meaning=key):
                report = deepcopy(original)
                report["baseline"]["lastFollowerTerminal"]["events"][key] = []
                with self.assertRaises(ValueError): route_control_measurements(report, manifest)

    def test_cleanup_manifest_must_match(self):
        report, manifest = fixture()
        manifest["observerControlCleanup"]["released"] = False
        with self.assertRaises(ValueError): route_control_measurements(report, manifest)

    def test_retained_e640_replay_when_available(self):
        directory = ROOT / "build/overworld-devtools/test-e640cfaf24d047ff83344047ebc518ba"
        if not (directory / "manifest.json").is_file():
            self.skipTest("optional local immutable memory data is absent")
        from tools.overworld.control import _replay_shared_test
        from tools.overworld.devtools_test_contract import validate_test
        test = validate_test(json.loads((ROOT / "tests/overworld/test-recipes/observation.live-route-control.json").read_text()))
        rows = [json.loads(line) for line in (directory / "observations.jsonl").read_text().splitlines()]
        replay = _replay_shared_test(test, rows)
        self.assertTrue(replay["passed"], replay.get("failures"))
        manifest = json.loads((directory / "manifest.json").read_text())
        self.assertEqual(len(route_control_measurements(replay["measurements"]["live-route-control-v1"], manifest)), 2)


if __name__ == "__main__": unittest.main()
