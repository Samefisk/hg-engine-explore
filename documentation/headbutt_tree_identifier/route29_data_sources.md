# Route 29 Tree Identifier Data Sources

## Coordinate Bounds

Route 29 is `MAP_R29 == 33`.

The map occupies three 32x32 cells on main matrix `0`:

- world x: `576..671`
- world y: `384..415`
- grid size: `96 x 32`

Matrix row `12`, columns `18..20` all have map value `33` for Route 29.
Their land-data chunks are files `1`, `2`, and `3`.

## Evidence Layers

The current verifier plan uses these independent layers:

- matrix stamps from `base/root/a/0/4/1`, file `0`
- land-file permission values from `base/root/a/0/6/5`, file `33`, only for coordinate sanity
- embedded visual map model from the same land file's `BMD0` / NSBMD section
- human labels in `route29.fixture.json`

The Headbutt archive is intentionally excluded. Do not use archive `treecoords` to find, count, match, or validate visual trees.

## Offline Audit

Dump the current deterministic coordinate/debug map with:

```bash
scripts/dump-route29-tree-grid.py \
  --output documentation/headbutt_tree_identifier/route29_grid_audit.json \
  --svg-output documentation/headbutt_tree_identifier/route29_grid_audit.svg
```

The script:

- parses the main matrix and Route 29's three stamps
- parses the land-file permission grid once and stamps it into world coordinates
- writes JSON plus a human-readable SVG overlay

This is not the input for tree counting. It does not exactly resemble the in-game visual map because it is the permission grid, not the rendered map model. Use it only to confirm world-coordinate bounds and matrix stamping.

The tree detector must be based on the visual layer or human-labeled in-game screenshot fixtures. Permission values can merge dense adjacent trees and are not sufficient for visual tree identity.

If live engine behavior becomes necessary, use a tiny row probe outside the cramped overworld-spawn overlay instead of exporting a 96x32 buffer from overlay memory.

## Verification

Detector output must be compared to `route29.fixture.json` with:

```bash
tools/headbutt_tree_identifier_verify.py \
  --fixture documentation/headbutt_tree_identifier/route29.fixture.json \
  --detections <detector-output.json>
```

The fixture is intentionally incomplete until the whole Route 29 tree labels are reviewed.
