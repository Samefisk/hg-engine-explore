"""Host-only known-bad controls for the permanent execution retirement check."""
from pathlib import Path
import tempfile
import unittest

from scripts.verify_overworld_devtools_only import (
    HISTORY_END, HISTORY_PATH, HISTORY_START, REPO, RETIRED_FILES,
    audit_data, audit_dependencies, audit_instructions, audit_python, audit_repository,
)


class RetirementSourceTests(unittest.TestCase):
    def test_desmume_imports_fail(self):
        for source in ("import desmume", "from desmume.emulator import DeSmuME",
                       "import desmume.controls as controls"):
            with self.subTest(source=source):
                self.assertEqual(audit_python(source, "scripts/runner.py")[0].code,
                                 "retired-emulator-import")

    def test_desmume_loader_constructor_and_process_calls_fail(self):
        for source in (
            "__import__('desmume.emulator')",
            "import importlib as lib\nlib.import_module('desmume')",
            "import importlib\nload = importlib.import_module\nload('desmume')",
            "import ctypes\nctypes.CDLL('/opt/libdesmume.dylib')",
            "from ctypes import CDLL as load\nnative = 'libdesmume.so'\nload(native)",
            "import ctypes\nload = ctypes.CDLL\nload('libdesmume.so')",
            "import importlib.util\nimportlib.util.spec_from_file_location('backend', root / 'desmume' / 'emulator.py')",
            "import importlib\nimportlib.import_module('des' + 'mume')",
            "import subprocess\nsubprocess.run(['python3', '-m', 'pip', 'install', 'py-desmume'])",
            "emu = DeSmuME()",
        ):
            with self.subTest(source=source):
                self.assertTrue(any(item.code == "retired-emulator-execution"
                                    for item in audit_python(source, "scripts/runner.py")))

    def test_desmume_save_format_and_history_do_not_fail(self):
        source = '''
# Historical evidence used DeSmuME.
FOOTER = b"DeSmuME savedata footer:"
BAD_IMPORT = "from desmume.emulator import DeSmuME"
BAD_LOADER = "ctypes.CDLL('libdesmume.so')"
from tools.overworld.melonds_backend import Emulator
def decode_save(data):
    if FOOTER not in data:
        raise ValueError("Not a DeSmuME DSV save")
'''
        self.assertEqual(audit_python(source, "scripts/save.py"), [])

    def test_desmume_dependency_fails_but_comment_is_history(self):
        for text in ("py-desmume==0.0.9", 'dependencies = ["py_desmume"]',
                     '"name": "py-desmume",'):
            with self.subTest(text=text):
                self.assertEqual(audit_dependencies(text, "requirements.txt")[0].code,
                                 "retired-emulator-dependency")
        self.assertEqual(audit_dependencies("# py-desmume was removed\nPillow\n", "requirements.txt"), [])

    def test_static_import_routes_fail(self):
        cases = (
            "import tools.overworld.runtime_normal_play as runtime",
            "from tools.overworld.runtime_actor_binding import observe",
            "from tools.overworld import runtime_normal_healing",
            "from .runtime_normal_play import Hooks",
            "import scripts.verify_overworld_walk_runtime",
        )
        for source in cases:
            with self.subTest(source=source):
                self.assertEqual(audit_python(source, "tools/overworld/engine.py")[0].code, "retired-import")

    def test_dynamic_loader_and_runpy_routes_fail(self):
        cases = (
            "import importlib.util\nspec = importlib.util.spec_from_file_location('driver', root / 'scripts/verify_overworld_walk_runtime.py')",
            "from importlib.util import spec_from_file_location as load\np = root / 'scripts' / 'headless-overworld-test.py'\nload('driver', p)",
            "import runpy\np = 'scripts/verify_overworld_walk_runtime.py'\nrunpy.run_path(p)",
            "from runpy import run_module as run\nrun('tools.overworld.runtime_normal_healing')",
            "import importlib as imports\nimports.import_module('tools.overworld.runtime_actor_binding')",
            "__import__('tools.overworld.runtime_normal_play')",
            "path = root / 'scripts/headless-overworld-test.py'\nsource = path.read_bytes()\nexec(compile(source, str(path), 'exec'), {})",
        )
        for source in cases:
            with self.subTest(source=source):
                self.assertTrue(any(item.code == "retired-execution" for item in audit_python(source, "scripts/worker.py")))

    def test_process_routes_and_indirect_constants_fail(self):
        cases = (
            "import subprocess\nsubprocess.run(['python3', 'scripts/verify_overworld_walk_runtime.py'])",
            "from subprocess import Popen as launch\ncommand = ['python3', 'scripts/headless-overworld-test.py']\nlaunch(command)",
            "import subprocess\nSCRIPT = 'scripts/verify_overworld_walk_runtime.py'\ndef run():\n command = ['python3', SCRIPT]\n subprocess.run(command)",
            "import os\nos.system('scripts/headless-test-ready.sh --rom test.nds')",
            "import asyncio\nasyncio.create_subprocess_exec('python3', 'scripts/verify_overworld_walk_runtime.py')",
            "import subprocess\nsubprocess.run(['python3', '-c', \"import runpy; runpy.run_path('scripts/verify_overworld_walk_runtime.py')\"])",
            "import subprocess as process\nlaunch = process.run\nlaunch(['python3', 'scripts/verify_overworld_walk_runtime.py'])",
        )
        for source in cases:
            with self.subTest(source=source):
                self.assertTrue(any(item.code == "retired-execution" for item in audit_python(source, "scripts/worker.py")))

    def test_host_and_battle_processes_are_not_banned(self):
        source = '''
import subprocess
import importlib.util
from tools.overworld.devtools_runtime import DevtoolsSession
subprocess.run(["cc", "-std=c11", "motion_model.c", "-o", "host-test"])
subprocess.run(["./host-test"])
subprocess.run(["python3", "scripts/run_tests.py"])
subprocess.run(["scripts/run_tests.sh"])
subprocess.run(["python3", "scripts/verify_overworld_mount.py"])
spec = importlib.util.spec_from_file_location("helper", "scripts/verify_overworld_spawn_profile_lifecycle.py")
'''
        self.assertEqual(audit_python(source, "tools/overworld/test_host.py"), [])

    def test_mutation_fixture_strings_and_comments_are_not_execution(self):
        source = '''
# Historical direct command: scripts/verify_overworld_walk_runtime.py
import re
pattern = re.compile(r"scripts/verify_overworld_walk_runtime.py")
BAD = "from tools.overworld.runtime_normal_play import Hooks"
def test_guard():
    source = "subprocess.run(['scripts/verify_overworld_walk_runtime.py'])"
    assert audit_python(source)
def test_host():
    source = "scripts/verify_overworld_mount.py"
    import subprocess
    subprocess.run(["python3", source])
'''
        self.assertEqual(audit_python(source, "tools/overworld/test_guard.py"), [])

    def test_syntax_error_fails_closed(self):
        self.assertEqual(audit_python("def bad(:", "scripts/worker.py")[0].code, "invalid-python")

    def test_active_scenario_and_registry_mutations_fail(self):
        for source in (
            '{"adapter":{"commands":[["python3","scripts/verify_overworld_walk_runtime.py"]]}}',
            '{"runners":{"scripts/verify_overworld_walk_runtime.py::wild_walk":[]}}',
            '{"checks":[{"command":["python3","scripts/headless-overworld-test.py"]}]}',
        ):
            with self.subTest(source=source):
                self.assertEqual(audit_data(source, "tests/overworld/scenarios/example.json")[0].code, "retired-runner")
        self.assertEqual(audit_data('{"commands":[["python3","scripts/run_tests.py"]]}', "features.yaml"), [])

    def test_active_instructions_fail(self):
        for text in (
            "Run `python3 scripts/verify_overworld_walk_runtime.py --scenario wild_walk`.",
            "Raw runtime runners are internal scenario/worker code, not an alternate agent workflow.",
            "The older headless launch scripts are backend code, not the agent workflow.",
            "Retire manual headless bootstrap workflows; retain backend dependencies until replaced.",
            "Run tests only when the user supplies test as a standalone sentence.",
            "Do not stop another session. Run scripts/verify_overworld_walk_runtime.py.",
            "Do not use the shared tools; run scripts/headless-overworld-test.py.",
        ):
            with self.subTest(text=text):
                self.assertEqual(audit_instructions(text, "AGENTS.md")[0].code, "retired-instruction")

    def test_retirement_notice_and_strict_proof_rules_remain_valid(self):
        source = """Do not run scripts/verify_overworld_walk_runtime.py.

Use owctl dev. A prepared spawn cannot prove a natural spawn.

Host ABI checks use scripts/verify_overworld_mount.py. Battle tests use scripts/run_tests.py.

No special build or test keyword is required. Unknown sessions must not be stopped.
"""
        self.assertEqual(audit_instructions(source, "AGENTS.md"), [])

    def test_backend_advice_cannot_cross_sentence_or_semicolon_boundaries(self):
        source = ("Do not use the old method. Root owns integration, this ledger and the one live session. "
                  "No helper may start a core or build. D1 gameplay claims remain pending.")
        self.assertEqual(audit_instructions(source, HISTORY_PATH), [])
        for source in ("Old method; helpers own integration; gameplay claims remain pending.",
                       "Old method! Helpers own integration. Gameplay claims remain pending."):
            self.assertEqual(audit_instructions(source, "AGENTS.md"), [])
        self.assertTrue(audit_instructions(
            "Old runtime helpers remain internal backends.", "AGENTS.md"))

    def test_explicit_ledger_history_does_not_hide_later_active_instructions(self):
        old = "Run scripts/verify_overworld_walk_runtime.py."
        source = f"{HISTORY_START}\n{old}\n{HISTORY_END}\n\n{old}"
        findings = audit_instructions(source, HISTORY_PATH)
        self.assertEqual([(item.line, item.code) for item in findings], [(5, "retired-instruction")])
        source = f"## Historical source reports\n{old}\n## Current work\n{old}"
        self.assertEqual([item.line for item in audit_instructions(source, HISTORY_PATH)], [4])

    def test_history_exemption_is_bounded_and_cannot_be_added_to_skills(self):
        for path, source in (
            (HISTORY_PATH, HISTORY_START + "\nold evidence"),
            (".agents/skills/verify-overworld/SKILL.md", HISTORY_START + "\nold evidence\n" + HISTORY_END),
        ):
            with self.subTest(path=path):
                self.assertTrue(any(item.code == "invalid-history-boundary" for item in audit_instructions(source, path)))


class RetirementRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for path in ("scripts", "tools/overworld", "tests/overworld/scenarios"):
            (self.root / path).mkdir(parents=True)
        self.put("AGENTS.md", "Use shared devtools.\n")

    def put(self, name, source):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)

    def test_complete_host_fixture_passes_then_each_retired_file_fails(self):
        self.assertTrue(audit_repository(self.root)["passed"])
        for name in RETIRED_FILES:
            with self.subTest(name=name):
                self.put(name, "# retained alias\n")
                report = audit_repository(self.root)
                self.assertFalse(report["passed"])
                self.assertTrue(any(item["path"] == name and item["code"] == "retired-file" for item in report["findings"]))
                (self.root / name).unlink()

    def test_repository_discovery_covers_code_json_skill_and_shell(self):
        self.put("scripts/worker.py", "from tools.overworld.runtime_normal_play import Hooks")
        self.put("scripts/launch.sh", "python3 scripts/verify_overworld_walk_runtime.py\n")
        self.put("tests/overworld/scenarios/example.json", '{"command":["scripts/headless-overworld-test.py"]}')
        self.put(".agents/skills/author-overworld-scenario/SKILL.md", "Run scripts/verify_overworld_walk_runtime.py.")
        report = audit_repository(self.root)
        self.assertEqual({item["code"] for item in report["findings"]},
                         {"retired-import", "retired-execution", "retired-runner", "retired-instruction"})

    def test_repository_discovery_covers_emulator_source_and_dependencies(self):
        self.put("scripts/worker.py", "from desmume.emulator import DeSmuME")
        self.put("scripts/launch.sh", "python3 -m pip install py-desmume\n")
        self.put("requirements.txt", "py-desmume==0.0.9\n")
        self.put("pyproject.toml", 'dependencies = ["py-desmume"]\n')
        report = audit_repository(self.root)
        self.assertEqual({item["code"] for item in report["findings"]},
                         {"retired-emulator-import", "retired-emulator-execution", "retired-emulator-dependency"})

    def test_historical_run_artifacts_and_unrelated_battle_are_out_of_scope(self):
        self.put("build/overworld-runs/failed.json", '{"command":["scripts/verify_overworld_walk_runtime.py"]}')
        self.put("documentation/old_attempts.md", "Run scripts/verify_overworld_walk_runtime.py.")
        self.put("scripts/battle.py", "import subprocess\nsubprocess.run(['python3', 'scripts/run_tests.py'])")
        self.assertTrue(audit_repository(self.root)["passed"])

    def test_empty_target_cannot_pass(self):
        report = audit_repository(self.root / "not-the-repository")
        self.assertFalse(report["passed"])
        self.assertEqual(report["findings"][0]["code"], "unexpected-target")


class CurrentRepositoryRetirementTests(unittest.TestCase):
    def test_active_repository_has_no_retired_execution_routes(self):
        report = audit_repository(REPO)
        summary = "\n".join(f'{item["path"]}:{item["line"]}: {item["code"]}'
                            for item in report["findings"])
        self.assertTrue(report["passed"], summary)


if __name__ == "__main__":
    unittest.main()
