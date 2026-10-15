import ast
from pathlib import Path
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
import __future__

from workshop_build_journal import BuildJournal


class BuildJournalTests(unittest.TestCase):
    def load_function(self, file, name, namespace):
        function = next(node for node in ast.parse(file.read_text()).body
                        if isinstance(node, ast.FunctionDef) and node.name == name)
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(file), "exec",
                     flags=__future__.annotations.compiler_flag), namespace)
        return namespace[name]

    def test_first_error_survives_tail_limit_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = BuildJournal(Path(directory))
            journal.save({"running": True, "output": "first compiler error\n"}, start=True)
            journal.append("warning\n" * 10000)
            state = BuildJournal(Path(directory)).restore(60000)
            self.assertLessEqual(len(state["output"]), 60000)
            self.assertTrue(journal.log.read_text().startswith("first compiler error\n"))
            self.assertFalse(state["running"])
            self.assertFalse(state["ok"])
            self.assertIn("unknown", state["error"])

    def test_completed_result_survives_and_new_build_resets_log(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = BuildJournal(Path(directory))
            journal.save({"running": True, "output": "old"}, start=True)
            journal.append(" done")
            journal.save({"running": False, "ok": True, "code": 0})
            self.assertTrue(journal.restore(100)["ok"])
            journal.save({"running": True, "output": "new"}, start=True)
            self.assertEqual(journal.log.read_text(), "new")

    def test_restart_rejects_active_build_before_thread_start(self):
        source = Path(__file__).with_name("overworld_behavior_profile_viewer.py").read_text()
        function = next(node for node in ast.parse(source).body
                        if isinstance(node, ast.FunctionDef) and node.name == "restart_server_soon")
        namespace = {"BUILD_LOCK": threading.Lock()}
        exec(compile(ast.Module(body=[function], type_ignores=[]), "restart", "exec"), namespace)
        namespace["BUILD_LOCK"].acquire()
        result = namespace["restart_server_soon"]()
        self.assertFalse(result["ok"])
        self.assertIn("Build is running", result["error"])

    def test_journal_write_failure_releases_both_build_entry_locks(self):
        root = Path(__file__).resolve().parents[1]
        for variant in ("legacy", "v2"):
            with self.subTest(variant=variant):
                lock = threading.Lock()
                failed_write = Mock(side_effect=OSError("disk unavailable"))
                namespace = dict(BUILD_LOCK=lock, update_build_state=failed_write,
                                 BUILD_COMMAND="build", TEST_NDS=Path("unused"),
                                 time=SimpleNamespace(time=lambda: 1))
                if variant == "legacy":
                    file = root / "scripts/overworld_behavior_profile_viewer.py"
                    args = ()
                else:
                    file = root / "tools/overworld-viewer-v2/reliability.py"
                    args = (SimpleNamespace(BUILD_LOCK=lock, update_build_state=failed_write,
                                            BUILD_COMMAND="build", TEST_NDS=Path("unused")), root)
                start = self.load_function(file, "start_build_job", namespace)
                with self.assertRaisesRegex(OSError, "disk unavailable"):
                    start(*args)
                self.assertTrue(lock.acquire(blocking=False))
                lock.release()

    def test_restart_holds_build_admission_until_exec_failure(self):
        lock = threading.Lock()
        pending = []
        def fake_thread(*, target, daemon):
            return SimpleNamespace(start=lambda: pending.append(target))
        namespace = dict(BUILD_LOCK=lock,
                         threading=SimpleNamespace(Thread=fake_thread),
                         time=SimpleNamespace(sleep=lambda seconds: None),
                         sys=SimpleNamespace(stdout=Mock(), stderr=Mock(), executable="python", argv=[]),
                         os=SimpleNamespace(execv=Mock(side_effect=OSError("exec failed"))))
        restart = self.load_function(Path(__file__).with_name("overworld_behavior_profile_viewer.py"),
                                     "restart_server_soon", namespace)
        self.assertTrue(restart()["ok"])
        self.assertFalse(lock.acquire(blocking=False))
        self.assertFalse(restart()["ok"])
        with self.assertRaisesRegex(OSError, "exec failed"):
            pending[0]()
        self.assertTrue(lock.acquire(blocking=False))
        lock.release()


if __name__ == "__main__":
    unittest.main()
