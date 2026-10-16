"""Disposable review ROM: an already-built ROM with only the map archives replaced.

  python3 -B -m tools.maps.review_rom [--base test.nds] [--out build/map-review/review.nds]

For looking at map changes when a full build is not possible (another
change in the tree does not link) or not needed (only land, events or matrix
members changed). The base ROM must already contain the same map headers
(IDs, banks): headers live in ARM9 and are not touched here. Area data is
replaced too. Never ship or copy this ROM to Delta; the real build is the
product.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import ndspy.rom

from . import cli, narc, world


def build(base_rom: Path, overrides: Path, out: Path) -> list[str]:
    base = world.load_base(world.RomSource(base_rom))
    edited = world.apply_overrides(base, overrides)
    for index, entry in enumerate(edited.headers):
        if index < len(base.headers) and {k: v for k, v in entry.items() if k != "name"} != \
                {k: v for k, v in base.headers[index].items() if k != "name"}:
            raise SystemExit(f"header {index} differs from the base ROM; a review ROM cannot change "
                             f"headers (ARM9). Do a full build.")
    rom = ndspy.rom.NintendoDSRom.fromFile(str(base_rom))
    changed = []
    for kind, path in world.ARCHIVE_PATHS.items():
        if edited.raw[kind] != base.raw[kind]:
            rom.setFileByName(path, narc.build(edited.raw[kind]))
            changed.append(f"{path} ({sum(a != b for a, b in zip(edited.raw[kind], base.raw[kind]))} members"
                           f"{', +%d' % (len(edited.raw[kind]) - len(base.raw[kind])) if len(edited.raw[kind]) != len(base.raw[kind]) else ''})")
    out.parent.mkdir(parents=True, exist_ok=True)
    rom.saveToFile(str(out))
    return changed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools.maps.review_rom", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", type=Path, default=cli.REPO / "test.nds")
    parser.add_argument("--overrides", type=Path, default=cli.REPO / "data/maps")
    parser.add_argument("--out", type=Path, default=cli.REPO / "build/map-review/review.nds")
    args = parser.parse_args(argv)
    changed = build(args.base, args.overrides, args.out)
    print(f"{args.out}: " + (", ".join(changed) if changed else "no map archive differs from the base"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
