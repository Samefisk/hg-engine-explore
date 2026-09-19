"""Factory policy checks require no emulator, ROM or native import."""
import ast
import builtins
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


class MelonDSBackendPolicyTests(unittest.TestCase):
    def test_native_build_manifest_records_resolved_cmake_executable(self):
        from tools.overworld.melonds_native import build as native_build
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private_bin = root / "private-bin"
            private_bin.mkdir()
            cmake = private_bin / "private-cmake"
            cmake.write_text("#!/bin/sh\nexit 0\n")
            cmake.chmod(0o700)
            source = root / "source"
            source.mkdir()
            native_output = root / "native-build"
            native_output.mkdir()
            filename = "libow_melonds.dylib" if sys.platform == "darwin" else "libow_melonds.so"
            (native_output / filename).write_bytes(b"native bridge")
            output = root / "output"
            argv = ["build.py", "--source", str(source), "--build-dir", str(native_output),
                    "--output", str(output), "--cmake", cmake.name]
            with patch.dict(os.environ, {"PATH": str(private_bin)}), \
                    patch.object(native_build, "prepare"), \
                    patch.object(native_build, "run") as run, \
                    patch.object(native_build.sys, "argv", argv):
                native_build.main()
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertEqual(manifest["cmakeExecutable"], str(cmake.resolve()))
            self.assertEqual(run.call_args_list[0].args[0][0], cmake.resolve())
            self.assertEqual(run.call_args_list[1].args[0][0], cmake.resolve())

    def test_changed_native_binary_is_rejected_before_loading(self):
        from tools.overworld import melonds_backend as backend
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            build=root/"build/melonds"
            build.mkdir(parents=True)
            source=root/"tools/overworld/melonds_backend.py"
            source.parent.mkdir(parents=True)
            filename="libow_melonds.dylib" if backend.sys.platform=="darwin" else "libow_melonds.so"
            (build/filename).write_bytes(b"changed library")
            (build/"manifest.json").write_text(json.dumps({
                "sourceRevision":backend.REVISION,
                "librarySha256":hashlib.sha256(b"original library").hexdigest()}))
            with patch.object(backend,"__file__",str(source)), patch.object(backend.C,"CDLL") as loader:
                with self.assertRaisesRegex(RuntimeError,"build identity differs"):
                    backend.load_library()
                loader.assert_not_called()

    def test_missing_melonds_never_imports_a_fallback(self):
        source = Path(__file__).with_name("devtools_native.py").read_text()
        tree = ast.parse(source)
        factory = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "create_emulator")
        namespace = {}
        exec(compile(ast.Module(body=[factory], type_ignores=[]), "factory", "exec"), namespace)
        calls = []
        def missing(name, *args, **kwargs):
            calls.append(name)
            raise ModuleNotFoundError(name)
        with patch.object(builtins, "__import__", side_effect=missing):
            with self.assertRaisesRegex(RuntimeError, "fallback is disabled"):
                namespace["create_emulator"]()
        self.assertEqual(calls, ["tools.overworld.melonds_backend"])
        imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        self.assertFalse(any(name and name.startswith("desmume") for name in imports))


if __name__ == "__main__":
    unittest.main()
