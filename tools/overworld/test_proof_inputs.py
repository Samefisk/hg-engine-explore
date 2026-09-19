"""Host-only scope regressions; no game execution or proof acceptance."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from . import proof_inputs as inputs
from .validation import ValidationFailure


class ProofInputsTests(unittest.TestCase):
    def setUp(self):
        inputs._CACHE.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.test = {"id": "walk.test", "requirements": ["legacy.test"], "actions": [{"op": "step"}]}
        for root in inputs.ROOTS:
            self.put(root, "# collector\n")
        self.put(inputs.REGISTRY, json.dumps({"sharedTests": {
            "walk.test": {"requirements": ["legacy.test"], "evaluator": "test"},
            "unrelated": {"requirements": []}},
            "measurementContracts": {"legacy.test": {"count": 1}, "other": {"count": 2}}}))
        self.put("tests/overworld/test-recipes/walk.test.json", json.dumps(self.test))
        self.put("src/product.c", "int product;\n")
        self.put("tools/overworld/devtools_example_proof.py", "# checker\n")
        self.put("tools/overworld/control.py", "# acceptance\n")
        self.put("tools/overworld/test_example.py", "# host test\n")
        self.put("tests/overworld/test-recipes/unrelated.json", "{}")
        self.put("tests/overworld/scenarios/unrelated.json", "{}")

    def put(self, path, value):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value)

    def scan(self, test=None):
        return inputs.proof_inputs(self.repo, test or self.test)

    def test_product_and_unknown_changes_require_capture(self):
        for name in ("src/product.c", "tools/overworld/new_shared.py"):
            before = self.scan()
            self.put(name, "# changed\n")
            self.assertNotEqual(before["capture"]["sha256"], self.scan()["capture"]["sha256"])

    def test_spawn_profile_population_inputs_require_fresh_capture(self):
        for name in (
            "data/overworld_behavior_profiles.json",
            "data/OverworldWildBehaviorData.c",
            "include/overworld_wild_behavior_data.h",
            "lib/overworld/overworld_population_model.c",
            "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c",
            "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c",
        ):
            with self.subTest(path=name):
                self.put(name, "before\n")
                before = self.scan()
                self.put(name, "after!\n")
                self.assertNotEqual(
                    before["capture"]["sha256"],
                    self.scan()["capture"]["sha256"],
                )

    def test_authored_and_job_normalized_route_have_identical_inputs(self):
        from .devtools_test_contract import validate_test
        root = Path(__file__).resolve().parents[2]
        raw = json.loads((root / "tests/overworld/test-recipes/observation.live-route-control.json").read_text())
        normalized = validate_test(raw)
        self.assertNotEqual(raw["actions"], normalized["actions"])
        self.put("tests/overworld/test-recipes/" + raw["id"] + ".json", json.dumps(raw))
        self.put(inputs.REGISTRY, json.dumps({"sharedTests": {raw["id"]: {
            "requirements": raw["requirements"]}}, "measurementContracts": {
                key: {"count": 1} for key in raw["requirements"]}}))
        self.assertEqual(self.scan(raw), self.scan(normalized))

    def test_checker_only_and_unrelated_tests(self):
        before = self.scan()
        self.put("tools/overworld/devtools_example_proof.py", "# new checker\n")
        after = self.scan()
        self.assertEqual(before["capture"], after["capture"])
        self.assertNotEqual(before["checker"], after["checker"])
        before = after
        for name in ("tools/overworld/test_example.py", "tests/overworld/test-recipes/unrelated.json",
                     "tests/overworld/scenarios/unrelated.json"):
            self.put(name, "# changed\n")
        self.assertEqual(before, self.scan())

    def test_existing_controller_owned_role_contracts_are_scoped(self):
        root = Path(__file__).resolve().parents[2]
        registry = json.loads((root / inputs.REGISTRY).read_text())
        self.put(inputs.REGISTRY, json.dumps(registry))
        for name in ("profile.owner-reader-control", "profile.follower-mounted-owner-transfer"):
            with self.subTest(name=name):
                authored = (root / "tests/overworld/test-recipes" / (name + ".json")).read_text()
                raw = json.loads(authored)
                self.put("tests/overworld/test-recipes/" + name + ".json", authored)
                before = self.scan(raw)
                self.put("tools/overworld/control.py", "# changed contract " + name)
                after = self.scan(raw)
                self.assertEqual(before["capture"], after["capture"])
                self.assertNotEqual(before["checker"], after["checker"])

    def test_missing_contract_without_implemented_adapter_fails(self):
        registry = json.loads((self.repo / inputs.REGISTRY).read_text())
        del registry["measurementContracts"]["legacy.test"]
        self.put(inputs.REGISTRY, json.dumps(registry))
        with self.assertRaises((ValidationFailure, ValueError)):
            self.scan()

    def test_controller_owned_scope_rejects_changed_registration(self):
        root = Path(__file__).resolve().parents[2]
        name = "profile.owner-reader-control"
        authored = (root / "tests/overworld/test-recipes" / (name + ".json")).read_text()
        raw = json.loads(authored)
        original = json.loads((root / inputs.REGISTRY).read_text())
        self.put("tests/overworld/test-recipes/" + name + ".json", authored)
        for fault in ("evaluator", "requirements", "claims", "recipeSha256", "mode", "subject"):
            with self.subTest(fault=fault):
                registry, test = copy.deepcopy(original), copy.deepcopy(raw)
                registration = registry["sharedTests"][name]
                if fault == "subject":
                    test["subjects"][0]["species"] = 155
                elif fault == "mode":
                    test["mode"] = "prepared"
                elif fault == "requirements":
                    registration[fault] = ["shared.unknown"]
                elif fault == "claims":
                    registration[fault] = ["controlled-action"]
                else:
                    registration[fault] = "unknown"
                self.put(inputs.REGISTRY, json.dumps(registry))
                with self.assertRaises(ValidationFailure):
                    self.scan(test)

    def test_collector_transitive_import_overrides_exclusion(self):
        self.put(inputs.ROOTS[1], "from . import devtools_example_proof\nfrom . import control\n")
        self.put("tools/overworld/devtools_example_proof.py", "from .test_example import value\n")
        self.put("tools/overworld/control.py", "from . import acceptance_dependency\n")
        self.put("tools/overworld/acceptance_dependency.py", "# unknown remains conservative\n")
        before = self.scan()
        self.put("tools/overworld/control.py", "# changed acceptance only\n")
        self.assertEqual(before["capture"], self.scan()["capture"])
        self.put("tools/overworld/test_example.py", "value = 2\n")
        self.assertNotEqual(before["capture"], self.scan()["capture"])

    def test_new_import_and_collector_change_require_capture(self):
        before = self.scan()
        self.put(inputs.ROOTS[2], "from tools.overworld import devtools_example_proof\n")
        after = self.scan()
        self.assertNotEqual(before["capture"], after["capture"])
        self.put("tools/overworld/devtools_example_proof.py", "# changed now-live dependency\n")
        self.assertNotEqual(after["capture"], self.scan()["capture"])

    def test_recipe_actions_and_scoped_registry(self):
        before = self.scan()
        changed = copy.deepcopy(self.test)
        changed["actions"][0]["op"] = "wait"
        self.assertNotEqual(before["capture"], self.scan(changed)["capture"])
        self.put("tests/overworld/test-recipes/walk.test.json", json.dumps(changed))
        self.assertNotEqual(before["capture"], self.scan()["capture"])
        before = self.scan()
        registry = json.loads((self.repo / inputs.REGISTRY).read_text())
        registry["sharedTests"]["unrelated"]["extra"] = True
        registry["measurementContracts"]["other"]["count"] = 9
        self.put(inputs.REGISTRY, json.dumps(registry))
        self.assertEqual(before, self.scan())
        registry["measurementContracts"]["legacy.test"]["count"] = 3
        self.put(inputs.REGISTRY, json.dumps(registry))
        after = self.scan()
        self.assertEqual(before["capture"], after["capture"])
        self.assertNotEqual(before["checker"], after["checker"])

    def test_missing_import_root_and_recipe_fail_closed(self):
        self.put(inputs.ROOTS[1], "from .absent import thing\n")
        with self.assertRaisesRegex(ValidationFailure, "import missing"):
            self.scan()
        self.put(inputs.ROOTS[1], "# valid\n")
        (self.repo / inputs.ROOTS[0]).unlink()
        with self.assertRaisesRegex(ValidationFailure, "input missing"):
            self.scan()
        self.put(inputs.ROOTS[0], "# restored\n")
        (self.repo / "tests/overworld/test-recipes/walk.test.json").unlink()
        with self.assertRaisesRegex(ValidationFailure, "input missing"):
            self.scan()

    def test_unknown_test_named_input_and_symlink_metadata_stay_bound(self):
        self.put("build-tools/test_product.py", "# unknown build input\n")
        before = self.scan()
        self.put("build-tools/test_product.py", "# changed build input\n")
        self.assertNotEqual(before["capture"], self.scan()["capture"])
        link = self.repo / "src/link.c"
        link.symlink_to("product.c")
        result = self.scan()
        record = inputs._record(self.repo.resolve(), Path("src/link.c"))
        self.assertEqual(record["symlink"], "product.c")
        link.unlink()
        link.symlink_to("../src/product.c")
        self.assertNotEqual(result["capture"], self.scan()["capture"])

    def test_unsafe_symlink_fails_even_for_excluded_host_test(self):
        target = self.repo / "tools/overworld/test_example.py"
        target.unlink()
        target.symlink_to("/etc/hosts")
        with self.assertRaisesRegex(ValidationFailure, "symlink leaves"):
            self.scan()

    def test_input_set_and_content_races_fail_closed(self):
        paths = inputs.runs._input_paths(self.repo)
        with patch.object(inputs.runs, "_input_paths", side_effect=[paths, paths[:-1]]):
            with self.assertRaisesRegex(ValidationFailure, "path set changed"):
                self.scan()
        original = inputs.runs._input_record
        inputs._CACHE.clear()
        def changed(repo, relative):
            result = original(repo, relative)
            if relative.as_posix() == inputs.ROOTS[0]:
                result["sha256"] = "0" * 64
            return result
        with patch.object(inputs.runs, "_input_record", side_effect=changed):
            with self.assertRaisesRegex(ValidationFailure, "changed during scan"):
                self.scan()

    def test_compact_result_and_stat_validated_cache(self):
        original = inputs.runs._input_record
        with patch.object(inputs.runs, "_input_record", wraps=original) as read:
            before = self.scan()
            first_reads = read.call_count
            self.assertGreater(first_reads, 0)
            self.assertEqual(before, self.scan())
            self.assertEqual(first_reads, read.call_count)
            target = self.repo / "src/product.c"
            old = target.stat()
            target.write_text("int changed;\n")  # Same size and restored mtime, but new ctime.
            os.utime(target, ns=(old.st_atime_ns, old.st_mtime_ns))
            self.assertEqual(old.st_size, target.stat().st_size)
            self.assertNotEqual(before["capture"], self.scan()["capture"])
            self.assertEqual(first_reads + 1, read.call_count)
        self.assertLess(len(json.dumps(before)), 5120)
        self.assertNotIn("files", before["capture"])
        before = self.scan()
        self.put("src/new.c", "new")
        added = self.scan()
        self.assertNotEqual(before["capture"], added["capture"])
        (self.repo / "src/new.c").unlink()
        self.assertEqual(before, self.scan())

    def test_selected_runner_claims_invalidate_checker_only(self):
        before = self.scan()
        registry = json.loads((self.repo / inputs.REGISTRY).read_text())
        registry["runners"] = {"legacy.test": ["live-actor-identity"]}
        registry["runnerKinds"] = {"legacy.test": "prepared"}
        self.put(inputs.REGISTRY, json.dumps(registry))
        after = self.scan()
        self.assertEqual(before["capture"], after["capture"])
        self.assertNotEqual(before["checker"], after["checker"])


if __name__ == "__main__":
    unittest.main()
