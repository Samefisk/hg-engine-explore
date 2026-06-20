#!/usr/bin/env python3
"""Report size pressure for the overworld wild overlays.

The report reads existing build artifacts. It does not build the ROM by itself,
so run the normal build first when the artifacts are missing or stale.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class OverlaySpec:
    overlay_id: int
    source_dir: str
    label: str


DEFAULT_OVERLAYS = (
    OverlaySpec(149, "overworld_wild_spawns_overlay", "spawns/runtime"),
    OverlaySpec(150, "overworld_wild_behavior_data_overlay", "behavior data"),
)


def parse_int(value: str) -> int:
    return int(value.strip(), 0)


def parse_linker_window(path: Path) -> tuple[int, int]:
    text = path.read_text()
    origin_match = re.search(r"\bORIGIN\s*=\s*(0x[0-9A-Fa-f]+|\d+)", text)
    length_match = re.search(r"\bLENGTH\s*=\s*(0x[0-9A-Fa-f]+|\d+)", text)
    if origin_match is None or length_match is None:
        raise ValueError(f"could not find ORIGIN/LENGTH in {path}")
    return parse_int(origin_match.group(1)), parse_int(length_match.group(1))


def run_nm(linked_object: Path) -> list[dict[str, object]]:
    nm = os.environ.get("NM")
    devkitarm = os.environ.get("DEVKITARM")
    candidates = []
    if nm:
        candidates.append(nm)
    if devkitarm:
        candidates.append(str(Path(devkitarm) / "bin" / "arm-none-eabi-nm"))
    candidates.extend(
        [
            "/opt/devkitpro/devkitARM/bin/arm-none-eabi-nm",
            "arm-none-eabi-nm",
            "nm",
        ]
    )

    last_error = None
    for candidate in candidates:
        try:
            output = subprocess.check_output(
                [candidate, "--print-size", "--size-sort", str(linked_object)],
                cwd=ROOT,
                stderr=subprocess.STDOUT,
                text=True,
            )
            return parse_nm_output(output)
        except (OSError, subprocess.CalledProcessError) as exc:
            last_error = exc

    raise RuntimeError(f"could not run nm for {linked_object}: {last_error}")


def parse_nm_output(output: str) -> list[dict[str, object]]:
    symbols = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        address, size, kind, name = parts[0], parts[1], parts[2], parts[3]
        if not re.fullmatch(r"[0-9A-Fa-f]+", size):
            continue
        symbols.append(
            {
                "address": int(address, 16),
                "size": int(size, 16),
                "kind": kind,
                "name": name,
            }
        )
    symbols.sort(key=lambda symbol: int(symbol["size"]), reverse=True)
    return symbols


def collect_overlay(spec: OverlaySpec, top: int) -> dict[str, object]:
    linker = ROOT / "src" / spec.source_dir / "linker.ld"
    build_binary = ROOT / "build" / f"output_{spec.source_dir}.bin"
    rom_binary = ROOT / "base" / "overlay" / f"overlay_{spec.overlay_id:04}.bin"
    linked_object = ROOT / "build" / f"{spec.source_dir}_linked.o"

    origin, length = parse_linker_window(linker)
    binary_path = build_binary if build_binary.exists() else rom_binary
    binary_size = binary_path.stat().st_size if binary_path.exists() else None
    headroom = None if binary_size is None else length - binary_size

    symbols = []
    nm_error = None
    if linked_object.exists():
        try:
            symbols = run_nm(linked_object)[:top]
        except RuntimeError as exc:
            nm_error = str(exc)

    return {
        "overlay_id": spec.overlay_id,
        "source_dir": spec.source_dir,
        "label": spec.label,
        "origin": origin,
        "length": length,
        "binary": str(binary_path.relative_to(ROOT)),
        "binary_size": binary_size,
        "headroom": headroom,
        "linked_object": str(linked_object.relative_to(ROOT)),
        "linked_object_exists": linked_object.exists(),
        "nm_error": nm_error,
        "top_symbols": symbols,
    }


def print_text_report(report: list[dict[str, object]]) -> None:
    print("Overworld wild overlay size report")
    print()
    for overlay in report:
        origin = int(overlay["origin"])
        length = int(overlay["length"])
        end = origin + length
        print(
            f"Overlay {overlay['overlay_id']} {overlay['source_dir']}"
            f" ({overlay['label']})"
        )
        print(f"  window: 0x{origin:08X}-0x{end:08X} ({length} bytes)")

        binary_size = overlay["binary_size"]
        if binary_size is None:
            print(f"  binary: missing ({overlay['binary']})")
            print("  headroom: unknown; run a build first")
        else:
            headroom = int(overlay["headroom"])
            status = "OVERFLOW" if headroom < 0 else "free"
            print(f"  binary: {overlay['binary']} ({binary_size} bytes)")
            print(f"  headroom: {abs(headroom)} bytes {status}")

        if not overlay["linked_object_exists"]:
            print(f"  symbols: missing ({overlay['linked_object']})")
        elif overlay["nm_error"]:
            print(f"  symbols: {overlay['nm_error']}")
        else:
            print("  top symbols:")
            for symbol in overlay["top_symbols"]:
                print(
                    "    "
                    f"{int(symbol['size']):5d} "
                    f"{symbol['kind']} "
                    f"{symbol['name']}"
                )
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="number of symbols to show per overlay",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON",
    )
    parser.add_argument(
        "--fail-on-overflow",
        action="store_true",
        help="return non-zero when a reported overlay exceeds its linker window",
    )
    args = parser.parse_args()

    report = [collect_overlay(spec, args.top) for spec in DEFAULT_OVERLAYS]

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_text_report(report)

    if args.fail_on_overflow:
        for overlay in report:
            headroom = overlay["headroom"]
            if headroom is not None and int(headroom) < 0:
                return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
