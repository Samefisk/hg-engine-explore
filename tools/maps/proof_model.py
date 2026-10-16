"""In-game proof that a generated NSBMD map model loads (test-only edit).

  python3 -B -m tools.maps.proof_model write    # replace land 257's model
  (build test.nds with hg-engine-delta-build)
  python3 -B -m tools.maps.proof_model probe    # live melonDS check, JSON out
  python3 -B -m tools.maps.proof_model remove   # take the edit out, rebuild

Land 257 is the back room of Elm's lab (map 62, T20R0102), used by no other
map. The edit keeps its tiles, buildings and BDHC and swaps only the model
for a generated flat floor named GENERATED_NAME. Probe reads which model the
loaded chunk points at (owctl terrain `landModels`), and checks that the map
stays loaded and the player can still walk. It does not judge how the room
looks; that needs a person.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import sys
from pathlib import Path

from . import cli, nsbmd, world
from .proof_route29 import _ow, _where

MAP_ID, LAND_ID, AREA_ID = 62, 257, 25
GENERATED_NAME = "gen_labo02"
VANILLA_NAME = "m_labo02_00_00c"
START, STEP_KEY = (10, 10), "LEFT"
SPEC = {
    "name": GENERATED_NAME,
    "materials": {"floor": {"texture": "01yuka_14", "palette": "01yuka_14_pl", "lit": False}},
    "tiles": [["floor" if x < 14 and z < 14 else None for x in range(32)] for z in range(32)],
    "height": 0,
    "merge": True,
}


def generated_model() -> bytes:
    source = world.RomSource(cli.REPO / "rom.nds")
    texset = nsbmd._area_texset(source, AREA_ID)
    data = nsbmd.write(nsbmd.grid_spec_to_model(SPEC, texset))
    errors, _warnings = nsbmd.validate(data, texset)
    if errors:
        raise SystemExit(f"generated model is invalid: {errors}")
    return data


def write(overrides: Path) -> None:
    land_dir = overrides / "land" / f"{LAND_ID:04d}"
    if land_dir.exists():
        raise SystemExit(f"{land_dir} already exists; refusing to mix with other edits")
    with contextlib.redirect_stdout(io.StringIO()):
        if cli.main(["--overrides", str(overrides), "checkout", "--map", str(MAP_ID), "--parts", "land"]):
            raise SystemExit("checkout failed")
    (land_dir / "model.nsbmd").write_bytes(generated_model())
    print(f"wrote generated model to {land_dir}")


def remove(overrides: Path) -> None:
    shutil.rmtree(overrides / "land" / f"{LAND_ID:04d}", ignore_errors=True)
    for folder in (overrides / "land", overrides):
        if folder.exists() and not any(folder.iterdir()):
            folder.rmdir()
    print("removed model proof edit")


def _model_names(terrain: dict) -> list[str]:
    names = []
    for chunk in (terrain.get("landModels") or {}).get("chunks", []):
        if chunk.get("known") and chunk.get("matrixIndex") == 0 and chunk.get("modelLoaded") == 1:
            for model in chunk["models"]:
                head = bytes.fromhex(model["headHex"])
                names += [name for name in (GENERATED_NAME, VANILLA_NAME) if name.encode() in head]
    return names


def probe(rom: str, save: str) -> int:
    _ow("start", "--rom", rom, "--save", save)
    try:
        _ow("teleport", str(MAP_ID), str(START[0]), str(START[1]), "--facing", "2")
        start = _where()
        terrain = _ow("terrain", "--x", str(START[0]), "--z", str(START[1]), "--radius", "0")
        terrain = terrain.get("terrain", terrain)
        names = _model_names(terrain)
        _ow("step", "8", "--keys", STEP_KEY)
        _ow("step", "60")
        after = _where()
    finally:
        _ow("stop")
    checks = {
        "teleportedIntoRoom": start == (MAP_ID, *START),
        "loadedChunkUsesGeneratedModel": names == [GENERATED_NAME],
        "mapStillLoadedAndWalkable": after[0] == MAP_ID and after[1] < START[0],
    }
    print(json.dumps({"start": start, "after": after, "loadedModelNames": names,
                      "checks": checks, "passed": all(checks.values())}))
    return 0 if all(checks.values()) else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tools.maps.proof_model", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("write", "probe", "remove"))
    parser.add_argument("--overrides", type=Path, default=cli.REPO / "data/maps")
    parser.add_argument("--rom", default="test.nds")
    parser.add_argument("--save", default="test.sav")
    args = parser.parse_args(argv)
    if args.action == "write":
        write(args.overrides)
    elif args.action == "remove":
        remove(args.overrides)
    else:
        return probe(args.rom, args.save)
    return 0


if __name__ == "__main__":
    sys.exit(main())
