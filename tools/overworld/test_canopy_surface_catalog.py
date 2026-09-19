"""Build-time controls for the native canopy surface catalog."""

import json
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

    def test_route29_uses_mesh_aligned_crown_rows_not_collision_edges(self):
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
        # tree footprint, the bottom row aligns with the billboard's high
        # crown edge. The known tree therefore resolves to world (594,389)
        # and (595,389), not the shoulder row above it.
        self.assertTrue(contains(1, 18, 3))
        self.assertTrue(contains(1, 19, 3))
        self.assertTrue(contains(1, 18, 5))
        self.assertTrue(contains(1, 19, 5))
        self.assertFalse(contains(1, 18, 4))

        # The compact-vertex face at the east edge supplies a crown on row 17,
        # but the behavior-6 shoulder row above it is still not a surface.
        # This guards against restoring the old collision-only heuristic.
        self.assertFalse(contains(1, 30, 16))
        self.assertFalse(contains(1, 31, 16))
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

        audit = {
            row["land_data_id"]: row["mesh"]
            for row in report["coverage"]["native_canopy_audit"]
            if row["land_data_id"] in (6, 7, 8)
        }
        self.assertEqual(set(audit), {6, 7, 8})
        self.assertTrue(
            all(mesh["ignored_non_horizontal_faces"] == 0 for mesh in audit.values())
        )


    def test_public_type_maps_to_canopy_and_adds_tree_top_height(self):
        header = (ROOT / "include/overworld_wild_behavior_data.h").read_text()
        generated_header = (
            ROOT
            / "include/constants/generated/overworld_wild_roof_catalog_counts.h"
        ).read_text()
        runtime = (
            ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"
        ).read_text()
        spawns = (
            ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
        ).read_text()
        hop_planner = (
            ROOT / "src/pokemon_move_history_task6_overlay/overworld_actor_hop_planner.c"
        ).read_text()
        validator = (ROOT / "scripts/validate_overworld_wild_blobs.py").read_text()
        self.assertIn("OW_WILD_SURFACE_TYPE_CANOPY 4", header)
        self.assertIn(
            "OW_WILD_SURFACE_CANOPY_HEIGHT_OFFSET_FX32 0x00031580",
            generated_header,
        )
        self.assertIn("OverworldWildSurfaceInstanceSizeMustRemain8Bytes", header)
        self.assertIn("u8 heightPageAndSurfaceType;", header)
        self.assertIn("? OW_WILD_BEHAVIOR_ALLOWED_TERRAIN_CANOPY", header)
        self.assertIn("OW_WILD_SURFACE_ID_NATIVE_GROUND\n            - (surfaceType >> 2)", runtime)
        self.assertIn("(u16)(hit.surfaceId + 2) > 1", runtime)
        self.assertIn(
            "return targetPosition.y + hit.height",
            runtime,
        )
        self.assertIn("hit.surfaceType == OW_WILD_SURFACE_TYPE_CANOPY", spawns)
        self.assertIn("1u << OW_WILD_SURFACE_TYPE_CANOPY", spawns)
        self.assertIn("targetSurface.height = OverworldWildSpawns_GetObjectGroundBaseYAt", spawns)
        self.assertIn(
            "hit.height += (s32)object->posVec[1]",
            spawns,
        )
        self.assertIn("(void)MapObject_RefreshHeightFromTerrain(object);", spawns)
        self.assertIn("obstacleBaseY = hit.height", hop_planner)
        self.assertIn("hit.surfaceId == OW_WILD_SURFACE_ID_NATIVE_CANOPY", hop_planner)
        self.assertIn("OWBD_SURFACE_CANOPY_HEIGHT_OFFSET_Q4 = 0x3158", validator)


if __name__ == "__main__":
    unittest.main()
