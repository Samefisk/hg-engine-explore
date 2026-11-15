"""Build-time controls for the native canopy surface catalog."""

import json
import os
import shlex
import subprocess
import tempfile
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.generate_overworld_wild_roof_catalog import (
    partition_tile_rectangles,
    read_land_permissions,
)
from tools.headbutt_tree_visual_model_probe import decode_vtx_10, decode_vtx_diff
from tools.narc_reader import NarcArchive
from scripts.verify_overworld_mount import function_body


CANOPY_HEIGHT_OFFSET_FX32 = 0x31580


class CanopySurfaceCatalogTests(unittest.TestCase):
    def test_compact_vertex_formats_expand_to_common_model_units(self):
        packed_vtx_10 = 32 | (16 << 10) | (160 << 20)
        packed_vtx_diff = 1 | (0x3FF << 10) | (2 << 20)

        self.assertEqual(
            decode_vtx_10(struct.pack("<I", packed_vtx_10)),
            (32 * 64, 16 * 64, 160 * 64),
        )
        self.assertEqual(
            decode_vtx_diff(struct.pack("<I", packed_vtx_diff)),
            (8, -8, 16),
        )

    def test_land_permissions_use_the_native_fixed_offset(self):
        archive = NarcArchive.from_file(ROOT / "base/root/a/0/6/5")
        data = archive.files[0]
        self.assertNotEqual(struct.unpack_from("<H", data, 18)[0], 0)
        expected = struct.unpack_from("<1024H", data, 0x14)
        self.assertEqual(read_land_permissions(archive, 0), expected)

    def test_dense_masks_are_split_to_fit_runtime_node_ids(self):
        tiles = {(x, y) for y in range(32) for x in range(32)}
        rectangles = partition_tile_rectangles(tiles)
        covered = {
            (x, y)
            for min_x, min_y, width, height in rectangles
            for y in range(min_y, min_y + height)
            for x in range(min_x, min_x + width)
        }
        self.assertEqual(covered, tiles)
        self.assertTrue(all(width * height <= 0xFF for _, _, width, height in rectangles))

    def test_checked_catalog_is_compressed_and_bounded(self):
        report = json.loads(
            (ROOT / "data/generated/overworld_wild_roof_catalog.json").read_text()
        )
        canopy = [row for row in report["instances"] if row["surface_type"] == "canopy"]
        native_flowerbeds = [
            row
            for row in report["instances"]
            if row["surface_type"] == "flowerbed"
            and row["height_mode"] == "native_ground"
        ]
        self.assertGreater(report["coverage"]["native_canopy_nodes"], 0)
        self.assertEqual(len(canopy), report["coverage"]["native_canopy_rectangles"])
        self.assertLess(len(canopy), report["coverage"]["native_canopy_nodes"])
        self.assertTrue(
            all(row["height_mode"] == "native_ground_offset" for row in canopy)
        )
        self.assertTrue(
            all(
                row["height_offset_fx32"] == CANOPY_HEIGHT_OFFSET_FX32
                for row in canopy
            )
        )
        self.assertTrue(
            all(row["height_q4"] == CANOPY_HEIGHT_OFFSET_FX32 >> 4 for row in canopy)
        )
        self.assertTrue(native_flowerbeds)
        self.assertTrue(all(row["height_q4"] == 0 for row in native_flowerbeds))
        self.assertEqual(report["coverage"]["native_canopy_excluded_matrix_ids"], [1])
        self.assertEqual(len(report["coverage"]["native_canopy_matrix_ids"]), 287)

        per_land = {}
        for row in report["instances"]:
            per_land[row["land_data_id"]] = per_land.get(row["land_data_id"], 0) + 1
        self.assertLessEqual(max(per_land.values()), 0xFF)

    def test_route29_uses_complete_mesh_tree_footprints_not_collision_edges(self):
        report = json.loads(
            (ROOT / "data/generated/overworld_wild_roof_catalog.json").read_text()
        )
        canopy = [row for row in report["instances"] if row["surface_type"] == "canopy"]

        def contains(land_data_id, x, y):
            return any(
                row["land_data_id"] == land_data_id
                and row["min_x"] <= x < row["min_x"] + row["width"]
                and row["min_y"] <= y < row["min_y"] + row["height"]
                for row in canopy
            )

        # Route 29 land block 1 begins at world (576, 384). In each 2x2 flat
        # tree footprint, both rows must support an adjacent Hop. The old
        # bottom-row-only mask rejected entry into the north half of a tree.
        self.assertTrue(contains(1, 18, 3))
        self.assertTrue(contains(1, 19, 3))
        self.assertTrue(contains(1, 18, 5))
        self.assertTrue(contains(1, 19, 5))
        self.assertTrue(contains(1, 18, 4))

        # Compact-vertex trees also expose their whole verified footprint.
        self.assertTrue(contains(1, 30, 16))
        self.assertTrue(contains(1, 31, 16))
        self.assertTrue(contains(1, 30, 17))
        self.assertTrue(contains(1, 31, 17))
        self.assertTrue(all(row["source"].startswith("land") for row in canopy))
        self.assertTrue(all(row["confidence"] == "mesh_verified" for row in canopy))

    def test_route30_includes_crowns_encoded_with_compact_vertices(self):
        report = json.loads(
            (ROOT / "data/generated/overworld_wild_roof_catalog.json").read_text()
        )
        canopy = [row for row in report["instances"] if row["surface_type"] == "canopy"]

        def contains(land_data_id, x, y):
            return any(
                row["land_data_id"] == land_data_id
                and row["min_x"] <= x < row["min_x"] + row["width"]
                and row["min_y"] <= y < row["min_y"] + row["height"]
                for row in canopy
            )

        # Route 30 uses compact vertices in all three of its land blocks.
        # These representative crowns were all dropped when those coordinates
        # were decoded at the wrong scale. The last point is world (546, 367).
        self.assertTrue(contains(6, 10, 3))
        self.assertTrue(contains(7, 17, 7))
        self.assertTrue(contains(8, 2, 15))
        # TKT-0078: from (561,364), Right enters this exact tree tile. Its
        # crown row already existed; the adjacent north row was missing.
        self.assertTrue(contains(8, 18, 12))
        self.assertTrue(contains(8, 18, 13))
        self.assertFalse(contains(8, 17, 12))


        audit = {
            row["land_data_id"]: row["mesh"]
            for row in report["coverage"]["native_canopy_audit"]
            if row["land_data_id"] in (6, 7, 8)
        }
        self.assertEqual(set(audit), {6, 7, 8})
        self.assertTrue(
            all(mesh["ignored_non_horizontal_faces"] == 0 for mesh in audit.values())
        )


    def run_native_height(self, *, omit_canopy_offset=False):
        source = (ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c").read_text()
        body = function_body(source, "OverworldWildRuntime_ResolveBaseYAt")
        if omit_canopy_offset:
            correct = "*output=position.y+(knownSurface != NULL ? knownSurface->height : 0);"
            self.assertEqual(body.count(correct), 1)
            body = body.replace(correct, "*output=position.y;")
        unit = r'''
#include <stdio.h>
#include <stddef.h>
typedef unsigned short u16;
typedef unsigned int u32;
typedef int s32;
typedef int BOOL;
typedef struct { s32 x,y,z; } VecFx32;
typedef struct { s32 nativeY; int available, calls; } FieldSystem;
typedef struct { s32 height; u16 surfaceId; } OverworldWildSurfaceHit;
#define TRUE 1
#define FALSE 0
#define MAPOBJECTFLAG_UNK23 (1u << 23)
#define MAPOBJECTFLAG_UNK29 (1u << 29)
#define OVERWORLD_PICKUP_ROUTE_SUPPORT_FLAG_MASK (MAPOBJECTFLAG_UNK23 | MAPOBJECTFLAG_UNK29)
#define OW_WILD_RUNTIME_FX32_ONE 4096
static BOOL Height(FieldSystem *field,VecFx32 *position,BOOL flag) {
    (void)flag;
    ++field->calls;
    if (!field->available) return FALSE;
    position->y=field->nativeY;
    return TRUE;
}
#define OW_WILD_RUNTIME_QUERY_NATIVE_HEIGHT Height
static BOOL Resolve(FieldSystem *fieldSystem,const OverworldWildSurfaceHit *knownSurface,
    s32 originBaseY,u32 objectFlags,int x,int y,s32 *output) {
''' + body + r'''
}
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"height failure line%d\n",__LINE__);return 1;} } while(0)
int main(void) {
    FieldSystem field={0x10000,1,0};
    OverworldWildSurfaceHit canopy={0x31580,0xFFFE}, roof={0x60000,1};
    s32 out=-7;
    CHECK(Resolve(&field,&canopy,0,0,594,388,&out) && out==0x41580 && field.calls==1);
    field.nativeY=0x20000;
    CHECK(Resolve(&field,&canopy,0,0,562,364,&out) && out==0x51580 && field.calls==2);
    CHECK(Resolve(&field,&roof,0,0,562,364,&out) && out==0x60000 && field.calls==2);
    CHECK(Resolve(&field,NULL,0,0,561,364,&out) && out==0x20000 && field.calls==3);
    field.available=0;out=-7;
    CHECK(!Resolve(&field,&canopy,0,0,562,364,&out) && out==-7 && field.calls==4);
    CHECK(!Resolve(NULL,&canopy,0,0,562,364,&out));
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix="canopy-native-height-") as temp:
            binary=Path(temp)/"height"
            compiled=subprocess.run([*shlex.split(os.environ.get("HOST_CC","cc")),
                "-std=c11","-O1","-x","c","-","-o",str(binary)],
                input=unit,text=True,capture_output=True,timeout=30)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            return subprocess.run([str(binary)],text=True,capture_output=True,timeout=10)

    def test_native_canopy_height_uses_checked_ground_and_preserves_roof_height(self):
        result=self.run_native_height()
        self.assertEqual(result.returncode,0,result.stderr)

    def test_missing_canopy_offset_is_rejected(self):
        result=self.run_native_height(omit_canopy_offset=True)
        self.assertNotEqual(result.returncode,0)
        self.assertIn("height failure",result.stderr)


if __name__ == "__main__":
    unittest.main()
