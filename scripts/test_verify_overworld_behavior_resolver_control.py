"""Failure-stage controls for the actual-C resolver rule-removal check."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest
from scripts import verify_overworld_behavior_resolver as verifier


class RuleRemovalControlTests(unittest.TestCase):
    def inputs(self):
        root = Path(__file__).resolve().parents[1]
        catalog = verifier._load_json(root / "data/overworld_behavior_profiles.json")
        application_id = catalog["runtimeBindings"]["defaultActiveApplication"]
        rule_index = verifier._application_indexes(root)[application_id]
        vectors = [dict(name="covered", request={}, expected=dict(requiredAppliedOverrideMask=1 << rule_index))]
        result = dict(status=0, profileHex="00" * 216)
        adapter = SimpleNamespace(resolve_many=Mock(side_effect=[[result], [result]]), build=Mock(return_value=root / "unused"))
        return root, vectors, adapter

    def test_compilation_or_execution_failure_is_not_rejection(self):
        for stage in ("build", "run"):
            root, vectors, adapter = self.inputs()
            if stage == "build": adapter.build.side_effect = RuntimeError("compiler failed")
            else: adapter.resolve_many.side_effect = [[dict(status=0)], RuntimeError("process failed")]
            with patch.object(verifier, "_verify_result"), self.assertRaises(RuntimeError):
                verifier.verify_rule_removal(root, root / "unused", vectors, adapter, root / "unused")

    def test_success_without_golden_difference_is_failure(self):
        root, vectors, adapter = self.inputs()
        with patch.object(verifier, "_verify_result"), self.assertRaisesRegex(AssertionError, "was accepted"):
            verifier.verify_rule_removal(root, root / "unused", vectors, adapter, root / "unused")

    def test_only_executed_successful_output_mismatch_counts(self):
        root, vectors, adapter = self.inputs()
        with patch.object(verifier, "_verify_result", side_effect=[None, AssertionError("wrong mask")]):
            result = verifier.verify_rule_removal(root, root / "unused", vectors, adapter, root / "unused")
        self.assertEqual(result["rejectedCases"], [dict(name="covered", reason="wrong mask")])
        self.assertEqual(adapter.resolve_many.call_count, 2)

    def test_source_anchor_rejects_missing_or_duplicate_seam(self):
        source = (Path(__file__).resolve().parents[1] / "lib/overworld/overworld_behavior_resolver.c").read_text()
        changed = verifier._remove_recorded_rule(source, 16)
        self.assertIn("if (index == 16) { return; }", changed)
        with self.assertRaises(ValueError): verifier._remove_recorded_rule("missing", 16)
        with self.assertRaises(ValueError): verifier._remove_recorded_rule(source + source, 16)
