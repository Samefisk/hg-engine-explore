"""Actual-body host controls for the Summary transport dependency migration."""
import argparse
import ast
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import shutil
from types import ModuleType, SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import os
import sys


ROOT = Path(__file__).resolve().parents[2]


def source_functions(path, names, namespace):
    source = path.read_text()
    tree = ast.parse(source)
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    if {node.name for node in selected} != set(names):
        raise AssertionError("actual function extraction is incomplete")
    body = "from __future__ import annotations\n" + "\n\n".join(ast.get_source_segment(source, node) for node in selected)
    exec(compile(body, str(path), "exec"), namespace)
    return namespace


def require(value, message):
    if not value:
        raise RuntimeError(message)


class SummaryNativeTransportTests(unittest.TestCase):
    def test_sealed_launcher_executes_only_retained_melonds_adapter(self):
        calls = []
        relative = "tools/overworld/melonds_backend.py"
        env = source_functions(ROOT / "scripts/launch_summary_move_relearn_runtime.py",
            ("_execute_runtime_modules",), {
                "RUNTIME_MODULE_RELATIVES": (relative,),
                "_execute_module": lambda *args: calls.append(args) or "retained-backend",
            })
        code = compile("sentinel = 1", "retained", "exec")
        self.assertEqual(env["_execute_runtime_modules"]({relative: code}, {relative: "sealed.py"}), "retained-backend")
        self.assertEqual(calls, [("summary_relearn_melonds_backend", "sealed.py", code)])

    def test_party_factory_uses_injected_transport_or_pinned_file_without_import_path_change(self):
        sentinel = object()
        env = source_functions(ROOT / "scripts/verify_pokemon_move_history_party_integrity.py",
            ("create_emulator",), {"AUTHENTICATED_HEADLESS": sentinel,
                "HEADLESS": SimpleNamespace(create_emulator=lambda: sentinel)})
        self.assertIs(env["create_emulator"](), sentinel)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tools/overworld/melonds_backend.py"
            path.parent.mkdir(parents=True)
            path.write_text("def MelonDS(): return 'only-melonds'\n")
            env = source_functions(ROOT / "scripts/verify_pokemon_move_history_party_integrity.py",
                ("create_emulator",), {"REPO": Path(directory), "ModuleType": ModuleType})
            before = list(sys.path)
            self.assertEqual(env["create_emulator"](), "only-melonds")
            self.assertEqual(sys.path, before)

    def test_native_preload_rejects_changed_library_and_rechecks_after_load(self):
        with tempfile.TemporaryDirectory() as directory:
            path = (Path(directory) / "libow_melonds.dylib").resolve()
            path.write_bytes(b"synthetic-native")
            digest = lambda value: {"size": len(value), "sha256": hashlib.sha256(value).hexdigest()}
            record = {"path": str(path), **digest(path.read_bytes())}
            env = source_functions(ROOT / "scripts/launch_summary_move_relearn_runtime.py",
                ("_preload_runtime_native", "_path_identity"), {
                    "os": os, "_require": require,
                    "_path_record": lambda value: digest(Path(value).read_bytes()),
                    "_validate_loaded_native_closure": lambda *args: None,
                })
            runtime = {"native": {"libmelonds": record}}
            handle = object()
            with patch("ctypes.CDLL", return_value=handle) as load:
                self.assertEqual(env["_preload_runtime_native"](runtime, None), (handle, str(path)))
                load.assert_called_once_with(str(path))
            path.write_bytes(b"changed-before-load")
            with patch("ctypes.CDLL") as load, self.assertRaisesRegex(RuntimeError, "differs before"):
                env["_preload_runtime_native"](runtime, None)
            load.assert_not_called()
            path.write_bytes(b"synthetic-native")
            def changed_during_load(*args):
                path.write_bytes(b"changed-across-load")
                return handle
            with patch("ctypes.CDLL", side_effect=changed_during_load), self.assertRaisesRegex(RuntimeError, "changed across"):
                env["_preload_runtime_native"](runtime, None)

    def test_active_summary_dependency_closure_contains_only_melonds_and_pillow(self):
        for relative in ("scripts/launch_summary_move_relearn_runtime.py",
                         "scripts/pokemon_move_history_build_manifest.py",
                         "scripts/generate_summary_move_relearn_native_inventory.py",
                         "scripts/verify_summary_move_relearn_runtime.py"):
            with self.subTest(relative=relative):
                source = (ROOT / relative).read_text()
                self.assertNotIn("desmume", source.lower())
        launcher = (ROOT / "scripts/launch_summary_move_relearn_runtime.py").read_text()
        self.assertIn("melonds_backend.configure_library(native_handle)", launcher)
        self.assertIn('"AUTHENTICATED_MELONDS_BACKEND": melonds_backend', launcher)

    def test_actual_fixed_boot_and_hold_keep_all_key_edges_and_counts(self):
        calls = []
        env = source_functions(ROOT / "tools/overworld/devtools_native.py",
            ("boot_to_ready", "hold_key"), {
                "cycle": lambda emu, frames, mask=None: calls.append(("cycle", frames, mask)),
                "tap_key": lambda emu, key, hold, gap: calls.append(("tap", key, hold, gap)),
                "key_constant": lambda key: 4,
                "keymask": lambda key: 1 << key,
                "set_key_mask": lambda emu, mask: calls.append(("mask", mask)),
            })
        boot = SimpleNamespace(boot_frames=420, ready_a_taps=10,
                               tap_hold_frames=24, tap_gap_frames=36, load_frames=300)
        self.assertEqual(env["boot_to_ready"](boot, None), 1320)
        self.assertEqual(calls, [("cycle", 420, None)] + [("tap", "A", 24, 36)] * 10 + [("cycle", 300, None)])
        calls.clear()
        env["hold_key"](None, "DOWN", 8, 60)
        self.assertEqual(calls, [("mask", 16), ("cycle", 8, 16), ("mask", 0), ("cycle", 60, None)])

    def fixture(self, directory, *, rejected=False, short=False, screenshot_failure=False):
        directory = Path(directory)
        rom, save, screenshot = (directory / name for name in ("source.nds", "source.sav", "frame.png"))
        rom.write_bytes(b"source-rom")
        save.write_bytes(b"source-save")
        state = {"cycles": 0, "reads": 0, "destroyed": False, "opened": None, "imported": None}

        def open_rom(path):
            state["opened"] = Path(path)
            self.assertNotEqual(Path(path), rom)
            self.assertEqual(Path(path).read_bytes(), b"source-rom")
            # Simulate a core-owned file write; it must not touch the source.
            Path(path).with_suffix(".dsv").write_bytes(b"core-battery-output")

        def import_save(path, force_size):
            state["imported"] = Path(path)
            self.assertNotEqual(Path(path), save)
            self.assertEqual(Path(path).read_bytes(), b"source-save")
            self.assertEqual(force_size, 0)
            if rejected:
                raise RuntimeError("melonDS rejected copied raw save")
            return None

        def image_save(path):
            if screenshot_failure:
                raise RuntimeError("image failed")
            Path(path).write_bytes(b"fresh-image")

        def read_party(emu):
            state["reads"] += 1
            return bytes([state["cycles"]]) * (7 if short else 8)

        emu = SimpleNamespace(volume_set=lambda value: None, open=open_rom,
            backup=SimpleNamespace(import_file=import_save),
            screenshot=lambda: SimpleNamespace(save=image_save),
            destroy=lambda: state.__setitem__("destroyed", True))
        helper = SimpleNamespace(silence_native_output=lambda enabled: nullcontext(),
            boot_to_ready=lambda args, core: state.__setitem__("boot", vars(args)),
            cycle=lambda core, frames: state.__setitem__("cycles", state["cycles"] + frames))
        env = source_functions(ROOT / "scripts/verify_pokemon_move_history_party_integrity.py",
            ("run_reload", "boot_arguments", "parse_args"), {
                "REPO": ROOT, "require": require, "Path": Path, "hashlib": hashlib,
                "os": os, "shutil": shutil, "tempfile": tempfile, "SimpleNamespace": SimpleNamespace,
                "HEADLESS": helper, "create_emulator": lambda: emu,
                "read_runtime_party": read_party, "PARTY_SIZE": 8, "argparse": argparse,
            })
        args = SimpleNamespace(rom=rom, reload_sav=save, reload_screenshot=screenshot)
        return env, args, state

    def test_reload_copies_inputs_observes_61_samples_and_cleans_owned_core(self):
        with tempfile.TemporaryDirectory() as directory:
            env, args, state = self.fixture(directory)
            result = env["run_reload"](args)
            self.assertEqual(state["cycles"], 60)
            self.assertEqual(state["reads"], 61)
            self.assertEqual([sample["frame"] for sample in result["actions"][0]["samples"]], list(range(61)))
            self.assertEqual(result["reads"][0]["value"], (bytes([60]) * 8).hex())
            self.assertTrue(result["sourceUnchanged"] and state["destroyed"])
            self.assertEqual(args.rom.read_bytes(), b"source-rom")
            self.assertEqual(args.reload_sav.read_bytes(), b"source-save")
            self.assertEqual(args.reload_screenshot.read_bytes(), b"fresh-image")
            self.assertFalse(state["opened"].exists())
            self.assertFalse(state["imported"].exists())
            self.assertFalse(args.rom.with_suffix(".dsv").exists())

    def test_import_read_and_image_failures_still_destroy_core_and_preserve_sources(self):
        for options, message in (({"rejected": True}, "rejected"), ({"short": True}, "incomplete"),
                                 ({"screenshot_failure": True}, "image failed")):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as directory:
                env, args, state = self.fixture(directory, **options)
                with self.assertRaisesRegex(RuntimeError, message):
                    env["run_reload"](args)
                self.assertTrue(state["destroyed"])
                self.assertEqual(args.rom.read_bytes(), b"source-rom")
                self.assertEqual(args.reload_sav.read_bytes(), b"source-save")

    def test_reload_rejects_input_overwrite_before_creating_core(self):
        with tempfile.TemporaryDirectory() as directory:
            env, args, state = self.fixture(directory)
            args.reload_screenshot = args.reload_sav
            with self.assertRaisesRegex(RuntimeError, "overwrite"):
                env["run_reload"](args)
            self.assertIsNone(state["opened"])

    def test_original_summary_mode_stays_valid_and_reload_has_no_general_driver_args(self):
        with tempfile.TemporaryDirectory() as directory:
            env, _, _ = self.fixture(directory)
            with patch.object(sys, "argv", ["party.py", "--dsv", "fixture.dsv"]):
                args = env["parse_args"]()
                self.assertEqual(args.dsv, Path("fixture.dsv"))
                self.assertIsNone(args.reload_sav)
            with patch.object(sys, "argv", ["party.py", "--reload-sav", "fixture.sav", "--reload-screenshot", "out.png"]):
                self.assertEqual(env["parse_args"]().reload_sav, Path("fixture.sav"))
            for flag in ("--action", "--read", "--scenario"):
                with self.subTest(flag=flag), patch.object(sys, "argv", ["party.py", "--reload-sav", "fixture.sav", flag, "arbitrary"]), \
                        patch.object(sys, "stderr"), self.assertRaises(SystemExit):
                    env["parse_args"]()

    def test_parent_reload_keeps_native_bootstrap_and_uses_only_typed_summary_mode(self):
        calls = []
        expected = b"expected-party"
        reply = {"actions": [{"samples": [{"reads": [{"value": b"stale".hex()}]},
                                             {"reads": [{"value": expected.hex()}]}]}],
                 "reads": [{"value": b"last".hex()}]}

        def native_runner(command, **kwargs):
            calls.append((command, kwargs))
            save = Path(command[command.index("--reload-sav") + 1])
            self.assertEqual(save.read_bytes(), b"raw-save")
            return SimpleNamespace(returncode=0, stderr="", stdout=json.dumps(reply))

        env = source_functions(ROOT / "scripts/verify_pokemon_move_history_party_integrity.py",
            ("reload_party_in_fresh_process",), {
                "REPO": ROOT, "require": require, "tempfile": tempfile, "json": json,
                "party_image": lambda raw: (1, 6, expected),
                "AUTHENTICATED_NATIVE_PREFIX": ("native-bootstrap", "--inventory", "sealed-inventory"),
                "AUTHENTICATED_NATIVE_RUNNER": native_runner,
                "AUTHENTICATED_NATIVE_CDHASH": "native-signature",
                "AUTHENTICATED_PYTHON_PATH": "repo-python",
                "AUTHENTICATED_CHILD_ENVIRONMENT": {"LC_ALL": "C"},
            })
        actual = env["reload_party_in_fresh_process"](Path("input.nds"), b"raw-save", Path("image.png"))
        self.assertEqual(actual, expected)
        command, options = calls[0]
        self.assertEqual(command[:3], ["native-bootstrap", "--inventory", "sealed-inventory"])
        self.assertIn(str(ROOT / "scripts/verify_pokemon_move_history_party_integrity.py"), command)
        self.assertIn("--reload-screenshot", command)
        self.assertTrue(set(command).isdisjoint({"--read", "--action", "--scenario"}))
        self.assertEqual(options["expected_cdhash"], "native-signature")
        self.assertEqual(options["child_environment"], {"LC_ALL": "C"})
        self.assertEqual(options["timeout"], 60)


@unittest.skipUnless(sys.platform == "darwin" and
                    (ROOT / "build/summary_move_relearn_native/summary_move_relearn_native_bootstrap").is_file(),
                    "requires the built macOS bootstrap; does not load an emulator")
class SummaryBootstrapLaunchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from scripts.generate_summary_move_relearn_native_inventory import build_inventory
        cls.inventory = ROOT / "scripts/summary_move_relearn_native_inventory.txt"
        cls.inventory_is_current = (
            cls.inventory.read_bytes() == build_inventory().encode("utf-8")
        )

    def require_current_inventory(self):
        if not self.inventory_is_current:
            self.skipTest(
                "sealed inventory is stale; regenerate with "
                "python3 scripts/generate_summary_move_relearn_native_inventory.py "
                "and reseal the native bootstrap"
            )

    def launch_help(self, relative):
        from scripts.summary_move_relearn_protected_spawn import run_native_bootstrap
        from scripts.verify_summary_move_relearn import (
            NATIVE_BOOTSTRAP_EXPECTED_SHA256, NATIVE_BOOTSTRAP_EXPECTED_CDHASH)
        inventory = self.inventory
        return run_native_bootstrap([
            str(ROOT / "build/summary_move_relearn_native/summary_move_relearn_native_bootstrap"),
            "--inventory", str(inventory), "--expected-inventory-sha256",
            hashlib.sha256(inventory.read_bytes()).hexdigest(),
            "--expected-self-sha256", NATIVE_BOOTSTRAP_EXPECTED_SHA256,
            "--", str(ROOT / ".venv/bin/python3"), "-I", "-S", "-B", "-X",
            "pycache_prefix=/dev/null", str(ROOT / relative), "--help"],
            expected_cdhash=NATIVE_BOOTSTRAP_EXPECTED_CDHASH,
            child_environment={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
            capture_output=True, text=True, timeout=60)

    def test_exact_party_helper_help_reaches_parser_without_core(self):
        self.require_current_inventory()
        result = self.launch_help("scripts/verify_pokemon_move_history_party_integrity.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--reload-sav", result.stdout)

    def test_other_sealed_python_source_is_not_an_allowed_entrypoint(self):
        self.require_current_inventory()
        result = self.launch_help("tools/overworld/melonds_backend.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Python invocation policy differs", result.stderr)

    def test_stale_inventory_fails_before_python_transport_policy(self):
        if self.inventory_is_current:
            self.skipTest("sealed inventory is current")
        result = self.launch_help("scripts/verify_pokemon_move_history_party_integrity.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("closure differs", result.stderr)


if __name__ == "__main__":
    unittest.main()
