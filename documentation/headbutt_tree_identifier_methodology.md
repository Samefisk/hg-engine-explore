# Headbutt Tree Identifier Methodology

## Goal

Identify each individual visual headbutt tree on a whole map before deriving canopy/top tiles.

The detector is not allowed to prove itself. A detected tree only counts as correct when it matches an independent human-labeled fixture.

The Headbutt archive must not be used to discover or validate individual trees. It is not reliable for visual tree identity.

## Ground Truth

Each fixture is a JSON file with:

- `map_id`: game map id, for Route 29 this is `33`.
- `coordinate_space`: the coordinate system used by labels and detections.
- `expected_trees`: one entry per human-labeled individual tree.
- `regions`: optional rectangular acceptance regions with expected counts.

Every expected tree should have a stable `id`, an approximate `anchor` coordinate, and optional notes. The anchor does not have to be the final canopy coordinate. It only needs to be a consistent point on the individual tree, such as the visual top-left tile or visual center tile.

## Detector Output

The detector writes JSON with:

- `map_id`
- `coordinate_space`
- `detected_trees`

Each detection must include:

- `id`
- `anchor`
- `bbox`
- `source`: for example `metatile_template`, `runtime_scan`, or `manual_probe`
- optional `confidence`
- optional `evidence`

## Verification

The verifier matches detections to expected labels with one-to-one matching. A detection can match a label by anchor distance, footprint overlap, or both.

It reports:

- matched trees
- false negatives: expected labels with no detection
- false positives: detections with no expected label
- duplicate pressure: multiple detections close to one expected label
- shape errors: matched trees whose footprint overlap is below the fixture threshold
- region count failures

Route 29 acceptance target:

- false negatives: `0`
- false positives: `0`, unless explicitly reviewed and added to the fixture
- split/merge pressure: `0`
- shape errors: `0` once those labels are filled
- region count failures: `0`
- anchor drift: at or below the fixture tolerance

## Reliability Checks

The same detector must be run from multiple camera/player positions. Runtime-only output is only reliable if the same world-coordinate tree set is produced regardless of viewport.

Required Route 29 runs:

- loaded Route 29 save, no movement
- after 5 RIGHT steps
- after 5 RIGHT then 5 LEFT steps
- at least one additional camera position that shows the dense left forest cluster

The same `expected_trees` fixture must be used for all runs.

## Current Known Fixture Region

The dense left forest square from the user screenshot must contain 12 individual trees. This is a region-level constraint until each of those 12 trees is labeled with anchors.

Do not continue to canopy/top-tile derivation until the whole-map Route 29 fixture passes.

## Route 29 Matrix And Land Data

Route 29 is three world cells:

- matrix `(18, 12)` -> map value `33`, land file `1`, world `576..607, 384..415`
- matrix `(19, 12)` -> map value `33`, land file `2`, world `608..639, 384..415`
- matrix `(20, 12)` -> map value `33`, land file `3`, world `640..671, 384..415`

All three matrix cells are Route 29 map value `33`, but they use different land-data chunks. That means a map-agnostic detector should identify local visual tree objects in each land file, then stamp them through the matrix into world coordinates.

The land-file permission grid is only a coordinate/debug layer. It is not tree identity by itself and it does not look like the in-game visual map. Dense forest areas can share one connected permission mass while containing many individual visual trees.

## Banned Source

Do not use Route 29 archive `treecoords` to find, count, match, or validate individual visual trees. They are not a reliable source for this task.
