"""Installed native own-spawn endpoint reader; host memory is not game proof."""
from copy import deepcopy
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import unittest

from tools.overworld.devtools_observer import NativeObservation, SPAWN_REFRESH_HEIGHT
from tools.overworld.test_devtools_reposition_observer import RepositionFixture


class SpawnHeightFixture(RepositionFixture):
    def __init__(self, directory):
        super().__init__(directory)
        self.observer.close()
        self.target = [552, 383]
        self.player["pos_y"] = 4096
        self.terrain = {"x": 552, "y": 383, "attribute": 2, "behavior": 2,
                        "provenance": {"fieldPointer": 0x02231000, "landDataId": 10}}
        self.rt.loaded_terrain_cell = lambda _emu, _x, _y: deepcopy(self.terrain)
        self.resolve = self.symbols["OverworldWildSpawns_ResolveObjectLandingHeight"]
        self.apply = self.symbols["OverworldWildSpawns_ApplySurfaceHeight"]
        regions = []
        for address, data in self.code_regions:
            if address in (self.resolve, self.apply):
                data = bytearray(data)
                data[8:12] = struct.pack("<HH", 0xF000, 0xF800)
                data = bytes(data)
                self.put(address, data)
            regions.append((address, data))
        self.code_regions = regions
        self.observer = NativeObservation(self, self.hooks, lambda _path, address, size: self.read(address, size))
        self.observer.install()

    def start(self):
        self.prepare_spawn(target=self.target)
        self.enter("spawn-prepared", r0=self.rt.WILD_STATE, r1=0x02231000, r2=0, r3=0)
        self.put(0x027E3788, struct.pack("<ii", *self.target))
        self.enter("spawn-motion", sp=0x027E3780, lr=0x02001101,
                   r0=self.rt.WILD_STATE, r1=0x02231000, r2=0, r3=self.source["object"])

    def height(self, *, point=None, object_pointer=None, caller=None):
        self.enter("spawn-landing-height", sp=0x027E3700, lr=(caller or self.timed) + 13,
                   r0=0x02231000, r1=object_pointer or self.source["object"], r2=(point or self.target)[0],
                   r3=(point or self.target)[1])
        self.player.update(x=self.target[0], y=self.target[1])

    def surface(self, *, result=1, surface_id=7, surface_type=3, height=8192,
                complete=True, point=None):
        self.put(0x02225000, struct.pack("<iHBB", height, surface_id, surface_type, 5))
        self.enter("spawn-landing-surface", sp=0x027E3600, lr=self.apply + 13,
                   r0=0x02231000, r1=(point or self.target)[0], r2=(point or self.target)[1], r3=0x02225000)
        if complete and not self.hooks.error:
            self.returned(result, sp=0x027E3600, address=self.apply + 12)

    def refresh(self, result=1):
        self.enter("spawn-landing-refresh-height", sp=0x027E3600, lr=self.resolve + 13,
                   r0=self.source["object"])
        if not self.hooks.error:
            self.returned(result, sp=0x027E3600, address=self.resolve + 12)

    def finish_height(self):
        self.player["pos_y"] = 8192
        self.returned(0xDEADBEEF, sp=0x027E3700, address=self.timed + 12)

    def finish(self):
        self.returned(1, sp=0x027E3780, address=0x02001100)
        self.returned(1)
        self.observer.completed_frame(12)
        return self.observer.drain()


class SpawnHeightObserverTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="spawn-height-observer-")
        self.addCleanup(self.directory.cleanup)
        self.f = SpawnHeightFixture(self.directory.name)

    def receipt(self):
        f = self.f
        self.assertIsNone(f.hooks.error)
        events = f.finish()
        self.assertIsNone(f.hooks.error)
        row = next(event["data"] for event in events if event["data"]["observation"] == "spawn-landing-height")
        spawn = next(event["data"] for event in events if event["data"]["observation"] == "spawn-prepared")
        self.assertEqual(spawn["jumpReceipts"][0]["landingHeight"], row)
        return row

    def test_actual_catalog_hit_and_position_are_not_legality_credit(self):
        f = self.f
        f.start(); f.height(); f.refresh(); f.surface(); f.finish_height()
        row = self.receipt()
        self.assertEqual(row["heightSource"], "catalog-surface")
        self.assertEqual(row["surfaceQuery"]["hit"], dict(height=8192, surfaceId=7, surfaceType=3, nodeId=5,
                         rawHex=struct.pack("<iHBB", 8192, 7, 3, 5).hex()))
        self.assertEqual(row["positionBefore"]["pos_y"], 4096)
        self.assertEqual(row["positionAfter"]["pos_y"], 8192)
        self.assertIsNone(row["returnValue"])
        self.assertEqual(row["loadedTerrain"]["cell"], f.terrain)
        self.assertEqual(row["surfaceLegality"], "unknown")
        self.assertFalse(row["acceptedProof"])

    def test_false_surface_does_not_read_uninitialized_hit(self):
        f = self.f
        f.start(); f.height(); f.refresh(); f.surface(result=0); f.finish_height()
        row = self.receipt()
        self.assertIsNone(row["surfaceQuery"]["hit"])
        self.assertEqual(row["heightSource"], "native-refresh")
        self.assertEqual(row["heightRefresh"]["returnValue"], 1)
        self.assertEqual(row["heightRefresh"]["positionBefore"]["flags"], f.player["flags"])
        self.assertEqual(row["heightRefresh"]["positionAfter"]["x"], f.target[0])
        self.assertEqual(row["surfaceLegality"], "unknown")

    def test_native_ground_surface_requires_actual_refresh(self):
        f = self.f
        f.start(); f.height(); f.refresh(); f.surface(surface_id=65535); f.finish_height()
        self.assertEqual(self.receipt()["heightSource"], "native-refresh")

    def test_failed_refresh_and_missing_terrain_stay_unknown(self):
        f = self.f; f.terrain = None
        f.start(); f.height(); f.refresh(0); f.surface(result=0); f.finish_height()
        row = self.receipt()
        self.assertEqual(row["heightSource"], "unknown")
        self.assertEqual(row["loadedTerrain"], {"status": "unknown", "cell": None})

    def test_wrong_object_is_rejected_at_installed_hook(self):
        f = self.f; f.start(); f.height(object_pointer=0x02210004)
        self.assertIn("field/object differs", f.hooks.error)

    def test_wrong_caller_is_rejected(self):
        f = self.f; f.start(); f.height(caller=f.apply)
        self.assertIn("wrong native caller", f.hooks.error)

    def test_intermediate_point_does_not_masquerade_as_target(self):
        f = self.f; f.start(); f.height(point=[551, 383])
        self.assertFalse(f.observer.spawn_height_contexts)
        self.assertEqual(f.observer.calls["spawn-landing-height"]["entered"], 0)

    def test_repeated_height_seeding_does_not_rescan_linked_symbols(self):
        class CountedSymbols(dict):
            scans = 0
            def values(self):
                self.scans += 1
                return super().values()
        f = self.f
        symbols = CountedSymbols(f.rt.WILD_SYMBOLS)
        f.rt.WILD_SYMBOLS = symbols
        f.start()
        for _ in range(16): f.height(point=[551, 383])
        self.assertIsNone(f.hooks.error)
        self.assertLessEqual(symbols.scans, 1)
        # The cached host bound must not bypass each live caller check.
        f.height(caller=f.apply)
        self.assertIn("wrong native caller", f.hooks.error)

    def test_wrong_surface_point_is_rejected(self):
        f = self.f; f.start(); f.height(); f.refresh(); f.surface(point=[551, 383])
        self.assertIn("point/order differs", f.hooks.error)

    def test_missing_surface_return_is_rejected(self):
        f = self.f; f.start(); f.height(); f.refresh(); f.surface(complete=False); f.finish_height()
        self.assertIn("missing surface return", f.hooks.error)

    def test_surface_before_refresh_is_rejected(self):
        f = self.f; f.start(); f.height(); f.surface(result=0); f.finish_height()
        self.assertIn("point/order differs", f.hooks.error)

    def test_canopy_uses_native_refresh_plus_catalog_offset(self):
        f = self.f
        f.start(); f.height(); f.refresh(); f.surface(surface_type=4, height=0x31580); f.finish_height()
        self.assertEqual(self.receipt()["heightSource"], "native-plus-catalog-offset")

    def test_world_change_is_rejected(self):
        f = self.f; f.start(); f.height(); f.refresh(); f.surface(); f.map_id += 1; f.finish_height()
        self.assertIn("source or world changed", f.hooks.error)

    def test_other_prepared_pokemon_cannot_borrow_this_native_object(self):
        f = self.f; f.start()
        f.observer.spawn_contexts[-1]["preparedEncounter"]["personality"] += 1
        f.height()
        self.assertIn("prepared encounter", f.hooks.error)

    def test_native_object_replaced_during_height_query_is_rejected(self):
        f = self.f; f.start(); f.height(); f.refresh(); f.surface()
        f.engine["active"] = False
        f.finish_height()
        self.assertIn("native object changed", f.hooks.error)

    def test_source_generation_changed_during_query_is_rejected(self):
        f = self.f; f.start(); f.height(); f.refresh(); f.surface()
        f.source["encounter_generation"] += 1
        f.finish_height()
        self.assertIn("source or world changed", f.hooks.error)

    def test_foreign_loaded_terrain_cannot_supply_provenance(self):
        f = self.f; f.terrain["provenance"]["fieldPointer"] += 4
        f.start(); f.height()
        self.assertIn("another point/world", f.hooks.error)

    def test_loaded_model_change_during_query_is_rejected(self):
        f = self.f; f.start(); f.height(); f.refresh(); f.surface()
        f.terrain["provenance"]["landDataId"] += 1
        f.finish_height()
        self.assertIn("loaded terrain changed", f.hooks.error)

    def test_missing_before_provenance_is_not_relabelled_as_observed(self):
        f = self.f; terrain = f.terrain; f.terrain = None
        f.start(); f.height(); f.refresh(); f.surface(); f.terrain = terrain; f.finish_height()
        row = self.receipt()
        self.assertEqual(row["loadedTerrainBefore"]["status"], "unknown")
        self.assertEqual(row["loadedTerrain"]["status"], "observed")
        self.assertEqual(row["surfaceLegality"], "unknown")

    def test_invalid_bool_is_rejected(self):
        f = self.f; f.start(); f.height(); f.refresh(); f.surface(result=2)
        self.assertIn("BOOL result differs", f.hooks.error)

    def test_missing_height_return_is_rejected_at_jump_return(self):
        f = self.f; f.start(); f.height()
        f.returned(1, sp=0x027E3780, address=0x02001100)
        self.assertIn("missing landing-height return", f.hooks.error)

    def test_actual_arm_declarations_and_surface_layout(self):
        root = Path(__file__).resolve().parents[2]
        product = (root / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
        declarations = []
        for name, result in (("ResolveObjectLandingHeight", "void"), ("QuerySurface", "BOOL")):
            match = re.search(r"\b(OverworldWildSpawns_" + name + r"\([^;{}]*\))\s*\{", product)
            self.assertIsNotNone(match)
            declarations.append(result + " " + match[1] + ";")
        source = '#include "map_events_internal.h"\n#include "overworld_wild_behavior_data.h"\n' + "\n".join(declarations) + '''
void (*resolve)(FieldSystem*,LocalMapObject*,int,int) = OverworldWildSpawns_ResolveObjectLandingHeight;
BOOL (*surface)(FieldSystem*,int,int,OverworldWildSurfaceHit*) = OverworldWildSpawns_QuerySurface;
BOOL (*refresh)(LocalMapObject*) = MapObject_RefreshHeightFromTerrain;
typedef char layout[(sizeof(OverworldWildSurfaceHit)==8
 && __builtin_offsetof(OverworldWildSurfaceHit,height)==0
 && __builtin_offsetof(OverworldWildSurfaceHit,surfaceId)==4
 && __builtin_offsetof(OverworldWildSurfaceHit,surfaceType)==6
 && __builtin_offsetof(OverworldWildSurfaceHit,nodeId)==7
 && OW_WILD_SURFACE_ID_NATIVE_GROUND==65535) ? 1 : -1];
'''
        with tempfile.TemporaryDirectory(prefix="spawn-height-abi-") as directory:
            path = Path(directory); (path / "abi.c").write_text(source)
            subprocess.run(["arm-none-eabi-gcc", "-w", "-Werror=incompatible-pointer-types", "-mthumb",
                            "-mcpu=arm7tdmi", "-I", str(root / "include"), "-c", str(path / "abi.c"),
                            "-o", str(path / "abi.o")], check=True)
        self.assertRegex((root / "rom.ld").read_text(),
                         r"MapObject_RefreshHeightFromTerrain\s*=\s*0x02061070\s*\|\s*1")
        self.assertEqual(SPAWN_REFRESH_HEIGHT, 0x02061070)


if __name__ == "__main__":
    unittest.main()
