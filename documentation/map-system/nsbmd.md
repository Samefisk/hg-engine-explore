# Map-chunk NSBMD: format, codec and generator

Tool: `tools/maps/nsbmd.py`. Tests: `python3 -B -m unittest tools.maps.test_nsbmd`.

```
python3 -B -m tools.maps.nsbmd roundtrip                      # 676/676 vanilla models, exit 0
python3 -B -m tools.maps.nsbmd generate --area 25 --spec grid.json --out chunk.nsbmd
python3 -B -m tools.maps.nsbmd rebuild --land 257 [--out f]   # vanilla geometry through the builder
python3 -B -m tools.maps.nsbmd info chunk.nsbmd [--area 25]   # summary + validation
```

`--rom` (before the subcommand) defaults to the repository `rom.nds`. The
output is the bare model; wrapping it into land_data is
`codecs.encode_land(spec, model)`.

## Verified format (all 676 land_data models)

`write(parse(b)) == b` holds for every model, also after a JSON round trip.
The parser rejects anything that would not round-trip. Nothing is kept as
opaque bytes. The envelope block would be kept as hex, but it is empty in
every vanilla chunk.

All offsets are little-endian. A *dictionary* is the NNS resource dictionary:
`u8 0, u8 count, u16 size; u16 8, u16 8+4(count+1)`, then count+1 Patricia
nodes `(refBit, left, right, entry)`, then `u16 unitSize, u16 namesOffset`,
the entries and 16-byte NUL-padded names. A name has no NUL only when it is
16 characters long. Building the tree: node 0 is the root (refBit 127, zero
key). Insert the names in order, splitting at the highest differing bit
(bit b = byte b>>3, bit b&7). Then **renumber the nodes in pre-order with the
left subtree first**. This reproduces every vanilla tree, including those in
the area NSBTX files.

| Part | Layout (vanilla order; each part directly follows the previous) |
|---|---|
| File | `BMD0`, BOM FEFF, version 2, size, header 16, 1 section, offset 0x14. No TEX0: textures come from the area NSBTX by name |
| MDL0 | `MDL0`, size, dictionary of models (entry = offset from MDL0). There is always exactly one model |
| Model header | `u32 size, sbc, mat, shp, evp` (relative to the model). Info: `u8 sbcType, scalingRule, texMtxMode, numNode, numMat, numShp, firstUnusedMtxStackId, 0; fx32 posScale, invPosScale; u16 numVertex, numPolygon, numTriangle, numQuad`. Box: `fx16 x,y,z,w,h,d; fx32 boxPosScale, boxInvPosScale` |
| Nodes | Dictionary at model+0x40, followed by node data: `u16 flag, fx16 m00`, then translation if !(flag&1), rotation if !(flag&2), and scale if !(flag&4). Vanilla uses one node with flag 0xF807 (identity); 5 models use 0xF806, which adds a translation |
| SBC | Typically `26 00 00 00 00` (NODEDESC with destination), `02 00 01` (NODE visible), `0B` (POSSCALE), then `04 m 05 s` pairs, `2B`, `01` RET, and zero padding to 4 bytes |
| Materials | `u16 texDictOfs, pltDictOfs`; material dictionary; texture dictionary; palette dictionary. Texture and palette entries are `u16 listOfs, u8 count, u8 bound=0`. Then the u8 material-index lists (textures first), padded to 4, then each material: `u16 0, u16 size, diffAmb, specEmi, polyAttr, polyAttrMask, texImageParam, texImageParamMask, u16 texPlttBase, flag, origW, origH, fx32 magW, magH`, plus optional texture-matrix data selected by flag bits 2/4/8/0x2000 |
| Shapes | Dictionary; 16-byte headers `u16 0, u16 16, u32 flag (1 normal, 2 color, 4 texcoord), u32 dlOfs (from the header), u32 dlSize`; then the display lists in order |
| Display list | GX packed words: 4 command bytes, low byte first, followed by their parameters (GBATEK counts). Every vanilla list ends with END_VTXS, NOP fill to a word boundary, and one more all-NOP word (3 lists have 2) |

Coordinates: vertex fx16 × posScale (usually 64) gives model units. A chunk
covers -256..256 on X and Z, with 16 units per tile. Tile column x maps to
X = -256+16x and tile row z maps to Z = -256+16z. This was checked by matching
water materials to water tile behaviors. On 671/676 models, decoding every
vertex form (VTX_16/10/XY/XZ/YZ/DIFF) reproduces the header box to within one
unit. The 5 exceptions carry a node translation. Header counts match the
display lists in 672/676 models. Lands 468, 473, 475 and 476 (all
`m_dun24xx` dungeon chunks) have stale counts in vanilla.

## Generator spec (`generate --spec`)

```json
{
  "name": "gen_chunk",
  "materials": {
    "floor": {"texture": "01yuka_14", "palette": "01yuka_14_pl", "lit": false},
    "grass": {"texture": "grass01", "palette": "grass01_pl", "tilesPerRepeat": 2,
              "lit": true, "alpha": 31, "doubleSided": false}
  },
  "tiles":   [["grass", "floor", null, ...32], ...32 rows],
  "fill":    "grass",
  "height":  0,
  "heights": [[0, ...33], ...33 rows],
  "quads":   [{"x": 5, "z": 8, "material": "floor", "heights": [nw, ne, se, sw],
               "uv": [[s,t] nw, ne, se, sw]}],
  "merge":   true
}
```

- `tiles` lists rows from north to south and columns from west to east. A
  null entry means no floor. `fill` is used when `tiles` is absent.
- `heights` gives corner heights in world units (16 per tile). `height`
  applies when `heights` is absent.
- A `quads` entry overrides one tile. Its `uv` values are in texels.
- Texture and palette names must exist in the area's `mapTileset` NSBTX
  (a/0/4/2 → a/0/4/4). The tool reads the texture size from that NSBTX and
  writes it as origW/H.
- UVs repeat the texture every `tilesPerRepeat` tiles. Give one int or
  `[x, z]`.
- Output: one material per key (sorted), one quad-list shape per used
  material, and a single node and SBC in vanilla form.
- `lit` materials copy the most common vanilla ground material: polyAttr
  0x1F8081, diffAmb 0x7FFFE739, normals. Unlit materials use 0x1F8080 and
  vertex color `color` (default white). Both use repeat S/T and fog.
- With `merge`, flat tiles that share a material and height are merged into
  rectangles. Each rectangle stays within ±2048 texels.
- Front faces point up, using vanilla winding: (b−a)×(c−a) is +Y.

`validate()` runs after generation and checks the following:

- The output parses and re-writes byte-for-byte.
- Every GX command has the right number of parameters.
- BEGIN/END are balanced, and the vertex counts fit each primitive type.
- The header counts equal the display-list counts.
- SBC indices are in range.
- Texture and palette names exist in the NSBTX.
- Size limits:
  - Error: more than 2048 polygons or 6144 vertices, which is one frame's
    hardware capacity.
  - Warning: more than the vanilla maximum of 1706 polygons, 4854 vertices or
    61420 bytes.

The `rebuild` check feeds every vanilla chunk's polygons and materials through
the same builder. The re-parsed geometry was identical for all 676 models.
The builder unrolls strips, so its output is larger than vanilla.

## Not verified

- **In-game loading and rendering.** No generated model has been loaded by
  the game yet. Name binding, visuals, culling and lighting are unproven.
- **The game's land_data/model buffer limit.** I did not find it in the
  decomp. Stay under the vanilla maximum.
- **Collision and heights.** The model does not provide them. Tiles and BDHC
  must be authored separately to match.
- **Texture-matrix materials** (flag 0x1FCF, texImageParam 0x40030000, used on
  animated water) and polygon IDs and translucency effects. These pass through
  the codec but the generator does not emit them.
- **Cracks.** Merged quads can leave small T-junction cracks next to sloped
  tiles. Set `"merge": false` if they appear.
