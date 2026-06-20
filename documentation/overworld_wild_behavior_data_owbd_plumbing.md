# Overworld Wild Behavior Data OWBD Plumbing

`CODE_ADDON_OVERWORLD_WILD_BEHAVIOR_DATA` is member `17` in `ARC_CODE_ADDONS`
(`a/0/2/8`). The build creates a pointerless `OWBD` binary at
`build/OverworldWildBehaviorData.bin` from
`data/overworld_wild_behavior/profiles.json` and copies it into
`build/a028/9_17` during `move_narc`.

The blob uses this resource shape:

- magic `OWBD`
- OWBD blob format version `1`
- fixed header size and total size
- payload size
- counts for profiles, class rules, species rules, and variable overrides
- relative offsets and element sizes for those sections
- CRC32 checksum with the checksum field zeroed

The persisted blob contains no absolute pointers. Section payloads are numeric
little-endian records matching the runtime C structs, with explicit padding and
4-byte-aligned section offsets.

Runtime overlay 150 now owns OWBD load, validation, and decode from
`ARC_CODE_ADDONS` member `CODE_ADDON_OVERWORLD_WILD_BEHAVIOR_DATA`. It decodes
into overlay-150 static storage and then exposes the same
`OverworldWildBehaviorDataOverlayEntry` ABI that overlay 149 already consumes.
Overlay 149 still owns behavior resolution; it only asks the overlay-150 entry
to ensure the OWBD cache has loaded before running its existing entry
validation.

The OWBD blob version is separate from the overlay entry ABI version
`OVERWORLD_WILD_BEHAVIOR_DATA_VERSION` (`19`). The entry ABI stays stable for
overlay 149 while the resource format has its own version field.

This PR intentionally uses fixed decode capacities matching the current source
data: 8 profiles, 2 class rules, 110 species rules, and 2 variable overrides.
The Python emitter and C decoder both fail closed if the JSON/resource grows
beyond those capacities.

Malformed or missing OWBD data makes the overlay-150 loader return `FALSE`.
Overlay 149 then treats the behavior data entry as unavailable and falls back
through its existing null-entry behavior paths.

Useful local checks:

```bash
python3 scripts/build_overworld_wild_behavior_data.py build --input data/overworld_wild_behavior/profiles.json --output build/OverworldWildBehaviorData.bin
python3 scripts/build_overworld_wild_behavior_data.py validate build/OverworldWildBehaviorData.bin --source-json data/overworld_wild_behavior/profiles.json --json
python3 scripts/build_overworld_wild_behavior_data.py roundtrip
python3 scripts/build_overworld_wild_behavior_data.py probe
make validate_owbd
```
