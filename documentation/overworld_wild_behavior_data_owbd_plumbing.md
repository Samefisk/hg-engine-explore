# Overworld Wild Behavior Data OWBD Plumbing

This branch reserves `CODE_ADDON_OVERWORLD_WILD_BEHAVIOR_DATA` as member `17` in
`ARC_CODE_ADDONS` (`a/0/2/8`). The build now creates a minimal `OWBD` binary at
`build/OverworldWildBehaviorData.bin` and copies it into `build/a028/9_17`
during `move_narc`.

The current blob is intentionally empty. It only validates the future resource
shape:

- magic `OWBD`
- version `1`
- fixed header size and total size
- payload size
- counts for profiles, class rules, species rules, and variable overrides
- relative offsets and element sizes for those sections
- CRC32 checksum with the checksum field zeroed

Runtime behavior is unchanged. No runtime code loads `CODE_ADDON_OVERWORLD_WILD_BEHAVIOR_DATA`
yet, and the overlay-150 C tables remain the active behavior data path.

The later JSON/codec branch should replace the dummy emitter with a source-backed
codec, likely from `data/overworld_wild_behavior/profiles.json`, while keeping
the same pointerless constraints: relative offsets, no absolute pointers, and
validation before any runtime cache decodes the blob.

Useful local checks:

```bash
python3 scripts/build_overworld_wild_behavior_data.py build --output build/OverworldWildBehaviorData.bin
python3 scripts/build_overworld_wild_behavior_data.py validate build/OverworldWildBehaviorData.bin --json
make validate_owbd
```
