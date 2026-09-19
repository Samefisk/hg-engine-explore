#!/usr/bin/env python3
"""Diagnostic object-only size probe; no ROM, source, or build-output writes.

Uses the existing build image and a read-only checkout. Temporary objects die
with the container. Results are compiler measurements, not gameplay proof.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("src/overworld_mount_overlay/overworld_mount_overlay.c")
FIELD_SOURCE = Path("src/field/overworld_mount_field_input.c")
FLAGS = ["-mthumb", "-mno-thumb-interwork", "-mcpu=arm7tdmi", "-mtune=arm7tdmi",
         "-mno-long-calls", "-march=armv4t", "-Os", "-fira-loop-pressure", "-fipa-pta"]


def worker(baseline=False):
    variants = [[], ["-fno-tree-forwprop"], ["-fno-tree-dominator-opts"],
                ["-fno-tree-fre"], ["-fno-caller-saves"], ["-fno-ipa-sra"],
                ["-fno-inline-small-functions"], ["-fno-tree-ter"],
                ["-fno-guess-branch-probability"]]
    if baseline:
        variants = [[]]
    results = []
    with tempfile.TemporaryDirectory(prefix="mount-object-") as temp:
        target = Path(temp) / "probe.o"
        for extra in variants:
            built = subprocess.run(["arm-none-eabi-gcc", *FLAGS, *extra,
                "-c", str(SOURCE), "-o", str(target)], capture_output=True, text=True)
            if built.returncode:
                raise RuntimeError(built.stderr[-4000:])
            output = subprocess.check_output(["arm-none-eabi-size", "-A", str(target)], text=True)
            sizes = {line.split()[0]: int(line.split()[1]) for line in output.splitlines()
                     if line.startswith(".")}
            # Include the assembly thunk: C section totals alone undercount
            # the linked precode reserve.
            thunk = Path(temp) / "thunk.o"
            subprocess.run(["arm-none-eabi-as", "-mthumb", "-mcpu=arm7tdmi",
                "asm/overworld_mount_overlay/thumb_runtime.s", "-o", str(thunk)], check=True)
            asm_output = subprocess.check_output(
                ["arm-none-eabi-size", "-A", str(thunk)], text=True)
            asm_sizes = {line.split()[0]: int(line.split()[1])
                         for line in asm_output.splitlines() if line.startswith(".")}
            sizes[".overworld_mount_boundary_thunk"] = asm_sizes[".overworld_mount_boundary_thunk"]
            if baseline:
                precode = sum(sizes[k] for k in (".overworld_mount_precode",
                    ".overworld_mount_hop_search", ".overworld_mount_streaming",
                    ".overworld_mount_boundary_thunk"))
                if precode > 0x328 or sizes[".overworld_mount_motion"] > 0x7B8:
                    raise RuntimeError(f"mount reserve overflow: precode={precode}, motion={sizes['.overworld_mount_motion']}")
            results.append(dict(flags=extra, sections=sizes,
                code=sum(v for k, v in sizes.items() if k == ".text" or
                         k.startswith(".overworld_mount_") and k not in
                         (".overworld_mount_state", ".overworld_mount_generation"))))
        built = subprocess.run(["arm-none-eabi-gcc", *FLAGS,
            "-c", str(FIELD_SOURCE), "-o", str(target)], capture_output=True, text=True)
        if built.returncode:
            raise RuntimeError(built.stderr[-4000:])
        output = subprocess.check_output(["arm-none-eabi-size", "-A", str(target)], text=True)
        results.append(dict(source=str(FIELD_SOURCE),
            sections={line.split()[0]: int(line.split()[1]) for line in output.splitlines()
                      if line.startswith(".")}))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    if sys.argv[1:] in (["--worker"], ["--worker", "--baseline"]):
        worker("--baseline" in sys.argv)
    elif sys.argv[1:] in ([], ["--baseline"]):
        if not (ROOT / SOURCE).is_file():
            raise SystemExit("mount source is missing")
        subprocess.run(["docker", "run", "--rm", "--network=none", "--workdir", "/hg-engine",
            "--mount", f"type=bind,source={ROOT},destination=/hg-engine,readonly",
            "hg-engine", "/usr/bin/python3", "scripts/probe_mount_object_size.py", "--worker", *sys.argv[1:]],
            check=True, timeout=120)
    else:
        raise SystemExit("usage: python3 scripts/probe_mount_object_size.py [--baseline]")
