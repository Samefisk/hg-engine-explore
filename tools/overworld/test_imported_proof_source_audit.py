"""Pure source-auditor controls; synthetic imports are data, never game drivers."""

from pathlib import Path
import unittest

from tools.overworld.validation import RuntimeProofSourceAudit


REPO = Path(__file__).resolve().parents[2]
COLLECTOR = "tools.overworld.runtime_normal_play"
OBSERVER = "tools.overworld.normal_play_observer"
CADENCE = "tools.overworld.runtime_cadence"
SPAWN_IDENTITY = "tools.overworld.spawn_identity"
RUNNER = '''
from tools.overworld.runtime_normal_play import run_case
def scenario_case():
    return run_case(runtime)
SCENARIOS = {"case": scenario_case}
'''


class ImportedProofSourceAuditTests(unittest.TestCase):
    def audit(self, source, *, runner=RUNNER, helpers=None, public=True):
        modules = {COLLECTOR: source, **(helpers or {})}
        return RuntimeProofSourceAudit(
            runner, local_module_sources=modules,
        ).audit("case", public_actor_evidence=public)

    def assert_rejected(self, source, kind, **kwargs):
        issues = self.audit(source, **kwargs)
        self.assertTrue(any(issue.startswith(kind + ":") for issue in issues), issues)

    def test_plain_imported_collector_passes(self):
        self.assertEqual(self.audit("def run_case(rt):\n    return {'passed': True}\n"), [])

    def test_module_alias_and_dotted_import_are_followed(self):
        for declaration, expression in (
            ("import tools.overworld.runtime_normal_play as normal", "normal.run_case"),
            ("import tools.overworld.runtime_normal_play", "tools.overworld.runtime_normal_play.run_case"),
            ("from tools.overworld import runtime_normal_play as normal", "normal.run_case"),
        ):
            with self.subTest(declaration=declaration):
                runner = f"{declaration}\ndef scenario_case():\n    return {expression}(runtime)\nSCENARIOS={{'case': scenario_case}}\n"
                self.assert_rejected("def run_case(rt):\n    return rt.MOUNT\n",
                                     "private-state-offset", runner=runner)

    def test_nested_callback_private_read_is_rejected(self):
        self.assert_rejected('''
def run_case(rt):
    def sample():
        return rt.movement_policy_state(emu, 7)
    register(sample)
''', "private-state-offset")

    def test_relative_import_is_followed(self):
        self.assert_rejected('''
from .normal_play_observer import check
def run_case(rt):
    return check()
''', "private-state-offset", helpers={OBSERVER: "def check():\n    return MOUNT\n"})

    def test_runtime_facade_alias_in_nested_callback_is_followed(self):
        self.assert_rejected('''
def run_case(rt):
    runtime_alias = rt
    def callback():
        return runtime_alias.measure()
    return callback()
''', "private-state-offset", runner=RUNNER + "def measure():\n    return MOUNT\n")

    def test_unknown_and_dynamic_imports_are_rejected(self):
        for source in (
            "import helper_module\ndef run_case(rt):\n    return helper_module.check()\n",
            "import importlib\ndef run_case(rt):\n    return importlib.import_module('helper_module').check()\n",
        ):
            issues = self.audit(source)
            self.assertTrue(any(issue.startswith("local-proof-routing/") for issue in issues), issues)

    def test_class_method_private_write_is_rejected(self):
        self.assert_rejected('''
class Collector:
    def sample(self):
        emu.memory.unsigned[0x023BA100] = 1
def run_case(rt):
    return Collector().sample()
''', "direct-private-state-write")

    def test_imported_class_helper_is_followed(self):
        self.assert_rejected('''
from tools.overworld.normal_play_observer import Recorder as R
def run_case(rt):
    return R().observe()
''', "private-state-offset", helpers={OBSERVER: '''
class Recorder:
    def observe(self):
        return helper()
def helper():
    return mount_state(emu)
'''})

    def test_imported_cadence_function_source_oracle_is_rejected(self):
        self.assert_rejected('''
from tools.overworld.runtime_cadence import evaluate
def run_case(rt):
    return evaluate()
''', "product-c-source-string", helpers={CADENCE: '''
def evaluate():
    return Path("src/actor.c").read_text()
'''})

    def test_import_time_side_effect_is_audited_even_if_unused(self):
        self.assert_rejected('''
UNUSED = movement_policy_state(emu, 7)
def run_case(rt):
    return True
''', "private-state-offset")

    def test_unreferenced_import_side_effect_is_audited(self):
        self.assert_rejected('''
from tools.overworld.normal_play_observer import unused
def run_case(rt):
    return True
''', "private-state-offset", helpers={OBSERVER: '''
PRIVATE = mount_state(emu)
def unused():
    return True
'''})

    def test_new_collector_cannot_import_legacy_raw_boundary(self):
        issues = self.audit('''
from tools.overworld import actor_probe
def run_case(rt):
    return True
''')
        self.assertTrue(any(issue.startswith("local-proof-routing/") for issue in issues), issues)

    def test_rt_attribute_and_runtime_value_follow_shared_runner(self):
        for expression, definition in (
            ("rt.measure()", "def measure():\n    return mount_state(emu)\n"),
            ("rt.ALIASED_OFFSET", "ALIASED_OFFSET = MOUNT + 4\n"),
        ):
            with self.subTest(expression=expression):
                self.assert_rejected(f"def run_case(rt):\n    return {expression}\n",
                                     "private-state-offset", runner=RUNNER + definition)

    def test_modified_public_transport_in_import_is_not_trusted(self):
        self.assert_rejected('''
def actor_state(emu, slot):
    return actor_memory_read(emu, 0x023BA100, 4)
def run_case(rt):
    return actor_state(emu, 7)
''', "public-transport-shadow")

    def test_imported_raw_actor_port_and_direct_read_are_rejected(self):
        for expression in (
            "rt.actor_memory_read(emu, 0x023BA100, 4)",
            "emu.memory.unsigned[0x023BA100]",
        ):
            with self.subTest(expression=expression):
                self.assert_rejected(f"def run_case(rt):\n    return {expression}\n",
                                     "raw-actor-memory-port")

    def test_imported_memory_alias_read_and_write_are_rejected(self):
        for statement, kind in (
            ("return alias[0x023BA100]", "private-state-offset"),
            ("alias[0x023BA100] = 1", "direct-private-state-write"),
        ):
            with self.subTest(statement=statement):
                self.assert_rejected("def run_case(rt):\n    port = emu.memory.unsigned\n"
                    f"    alias = port\n    {statement}\n", kind)

    def test_numeric_private_read_via_generic_runtime_reader_is_rejected(self):
        for expression in ("0x023BA100", "address"):
            self.assert_rejected("def run_case(rt):\n    address = 0x023BA100\n"
                f"    return rt.unsigned(emu, {expression}, 4)\n", "private-state-offset")

    def test_callback_default_argument_is_audited(self):
        self.assert_rejected('''
def run_case(rt):
    def callback(value=mount_state(emu)):
        return value
    return callback()
''', "private-state-offset")

    def test_missing_or_unregistered_import_fails_closed(self):
        for module in (OBSERVER, "tools.overworld.unregistered_helper"):
            with self.subTest(module=module):
                issues = self.audit(f"from {module} import helper\ndef run_case(rt):\n    return helper()\n")
                self.assertTrue(any(issue.startswith("local-proof-routing/") for issue in issues), issues)

    def test_malformed_or_missing_export_fails_closed(self):
        for source in ("def broken(", "def other():\n    return True\n"):
            issues = self.audit("from tools.overworld.normal_play_observer import helper\ndef run_case(rt):\n    return helper()\n",
                                helpers={OBSERVER: source})
            self.assertTrue(any(issue.startswith("local-proof-routing/") for issue in issues), issues)

    def test_fault_helper_cannot_return_private_oracle(self):
        self.assert_rejected('''
def fault_inject_case(emu):
    return mount_state(emu)
def run_case(rt):
    return fault_inject_case(emu)
''', "fault-hook-result")


class ActualPureObserverSourceAuditTests(unittest.TestCase):
    """Audit the retained pure observer, never a retired game driver."""
    @classmethod
    def setUpClass(cls):
        cls.observer = (REPO / "tools/overworld/normal_play_observer.py").read_text()
        cls.entry = """
from tools.overworld.normal_play_observer import MotionRecorder
def scenario_case():
    return MotionRecorder().observe(frame, actor, engine)
SCENARIOS = {"case": scenario_case}
"""

    def issues(self, observer, helpers=None):
        return RuntimeProofSourceAudit(self.entry, repo=REPO,
            local_module_sources={OBSERVER: observer, **(helpers or {})}).audit(
            "case", public_actor_evidence=True)

    def test_actual_pure_observer_import_closure_passes(self):
        self.assertEqual(self.issues(self.observer), [])

    def test_spawn_identity_helper_is_audited_not_trusted(self):
        source = "def live_spawn_flags(value):\n    return mount_state(emu)\n"
        issues = self.issues(self.observer, {SPAWN_IDENTITY: source})
        self.assertTrue(any(issue.startswith("private-state-offset:") for issue in issues), issues)

    def test_actual_imported_class_private_state_mutation_is_rejected(self):
        original = "def observe(self, frame, actor, engine):"
        self.assertEqual(self.observer.count(original), 1)
        mutated = self.observer.replace(
            original, original + "\n        state = movement_policy_state(emu, 7)", 1)
        self.assertTrue(any(issue.startswith("private-state-offset:")
                            for issue in self.issues(mutated)))


if __name__ == "__main__":
    unittest.main()
