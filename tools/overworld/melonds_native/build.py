#!/usr/bin/env python3
"""Build the pinned shared melonDS transport; no ROM or save is opened."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

if __package__:
    from .prepare_source import prepare, REVISION
else:
    from prepare_source import prepare, REVISION


def run(args):
    subprocess.run([str(x) for x in args], check=True)


def resolve_executable(command):
    executable = shutil.which(str(command))
    if executable is None:
        raise FileNotFoundError(f"CMake executable not found: {command}")
    return Path(executable).resolve()


def main():
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="disposable official 1.1 checkout")
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--output", type=Path, default=here.parents[2] / "build/melonds")
    parser.add_argument("--cmake", default="cmake")
    args = parser.parse_args()
    cmake = resolve_executable(args.cmake)
    def inputs():
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(here.iterdir()) if p.suffix in (".cpp", ".h", ".py", ".txt")}
    owned = inputs()
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.source or args.output / "source"
    if not source.exists():
        run(["git", "clone", "--depth", "1", "--branch", "1.1", "https://github.com/melonDS-emu/melonDS.git", source])
    prepare(source)
    build = args.build_dir or args.output / "native-build"
    run([cmake, "-S", here, "-B", build, f"-DMELONDS_SOURCE={source.resolve()}", "-DCMAKE_BUILD_TYPE=Release"])
    run([cmake, "--build", build, "--parallel", "6"])
    run([build / "ow_melonds_core_test"])
    if inputs() != owned:
        raise RuntimeError("bridge source changed during build; no library installed")
    filename = "libow_melonds.dylib" if sys.platform == "darwin" else "libow_melonds.so"
    library = args.output / filename
    shutil.copy2(build / filename, library)
    manifest = {"schemaVersion": 1, "sourceRevision": REVISION, "sourceTag": "1.1", "sourceRepository": "https://github.com/melonDS-emu/melonDS.git", "librarySha256": hashlib.sha256(library.read_bytes()).hexdigest(), "bridgeInputs": owned, "cmakeExecutable": str(cmake), "jit": False, "renderer": "software", "coreTests": "passed-no-ROM", "abiVersion": 1}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"library": str(library), "manifest": str(args.output / "manifest.json"), "coreTests": "passed-no-ROM"}))


if __name__ == "__main__":
    main()
