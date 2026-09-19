"""Host-only receipt controls; no game acceptance or geometry claim."""
from copy import deepcopy
from pathlib import Path
import struct
import unittest

from tools.overworld.test_devtools_spawn_measurement import fixture, AUTHORED, SOURCE
from tools.overworld.test_devtools_chain_measurement import Stream
from tools.overworld.devtools_spawn_surface_measurement import check_pool_spawn_surface


def surface_fixture():
    spawn = fixture()
    stream = Stream()
    stream.motion("HOP", (16, 0), pause=2, spawn=True)
    snapshot = deepcopy(stream.items[-1][0])
    actor = snapshot["actors"][0]
    engine = actor["engineIdentity"]
    engine["id_lookup"] = {"eligible_count": 1, "pointer_matches": True}
    state = deepcopy(actor["engineObject"])
    clock = {"actorFrame": 1, "nativeCycle": 2}
    field = spawn["fieldPointer"]
    cell = {"x": 16, "y": 0, "attribute": 2, "behavior": 2, "collision": False,
            "terrain_class": 0, "matrix_index": 0, "block": 0,
            "provenance": {"fieldPointer": field, "mapMatrixPointer": 0x02040000,
                "matrixId": 1, "matrixWidth": 2, "matrixHeight": 2,
                "mapHeaderId": 34, "landDataId": 5, "landDataIdentity": "current-map-matrix",
                "attributeAddress": 0x02050000, "rawWord": 2, "store": "full-terrain-attributes"}}
    height = {"status": "observed", "observationVersion": 1,
        "slot": spawn["slot"], "sourceIdentity": deepcopy(actor["sourceIdentity"]),
        "engineIdentity": deepcopy(engine), "engineIdentityAfter": deepcopy(engine),
        "worldContext": deepcopy(spawn["worldContext"]), "target": [16, 0],
        "preparedPointer": spawn["preparedPointer"], "preparedEncounter": deepcopy(spawn["preparedEncounter"]),
        "positionBefore": deepcopy(state), "positionAfter": deepcopy(state),
        "entryActorFrame": 1, "returnActorFrame": 1, "entryNativeCycle": 2, "returnNativeCycle": 2,
        "surfaceQuery": {"kind": "surface", "point": [16, 0], "returnValue": 0,
            "hit": None, "entry": clock, "returned": clock},
        "heightRefresh": {"kind": "height-refresh", "objectPointer": engine["pointer"],
            "returnValue": 1, "positionBefore": deepcopy(state), "positionAfter": deepcopy(state),
            "entry": clock, "returned": clock},
        "loadedTerrainBefore": {"status": "observed", "cell": deepcopy(cell)},
        "loadedTerrain": {"status": "observed", "cell": cell},
        "heightSource": "native-refresh", "nativeReturnKind": "void", "returnValue": None}
    jump = spawn["jumpReceipts"][0]
    jump.update(sourceIdentity=deepcopy(actor["sourceIdentity"]), landingHeight=height)
    return spawn, snapshot


def check(spawn, snapshot):
    return check_pool_spawn_surface(spawn, snapshot, source_sha256=SOURCE, authored_profiles=AUTHORED)


class PoolSpawnSurfaceTests(unittest.TestCase):
    def test_verified_zero_elapsed_successor_does_not_require_idle_gap(self):
        spawn, snapshot = surface_fixture()
        actor = snapshot["actors"][0]
        actor.update(motionPhase="MOVING", motionKind="WALK", motionElapsed=0, reservationId=4,
                     origin={"x": 16, "y": 0}, target={"x": 17, "y": 0})
        actor["engineObject"]["x"] = 17  # Admission can already own the next logical tile.
        actor["engineObject"]["flags"] = 1098755  # Recorded elapsed0 successor at frame1170.
        boundary = {"kind": "terminal-with-unmeasured-successor", "frame": snapshot["frame"],
            "completedCommit": actor["commitSequence"], "successor": {"handle": deepcopy(actor["handle"]),
                "kind": "WALK", "origin": [16, 0], "target": [17, 0], "elapsed": 0, "countedAsComplete": False}}
        def run():
            return check_pool_spawn_surface(spawn, snapshot, source_sha256=SOURCE,
                authored_profiles=AUTHORED, verified_stop_boundary=boundary)
        self.assertTrue(run()["passed"])
        for key in ("frame", "completedCommit"):
            boundary[key] += 1
            with self.assertRaises(ValueError): run()
            boundary[key] -= 1
        actor["motionElapsed"] = 1
        with self.assertRaises(ValueError): run()
        actor["motionElapsed"] = 0
        actor["engineObject"]["pos_y"] += 1
        with self.assertRaises(ValueError): run()

    def test_valid_native_land(self):
        self.assertTrue(check(*surface_fixture())["passed"])

    def test_unknown_or_wrong_receipts_fail_closed(self):
        for fault in ("missing", "failed", "ignored", "point", "object", "world", "pid", "height",
                      "terminal-object", "terminal-world", "terminal-pid", "moving", "unloaded", "collision",
                      "raw-word", "source", "future", "missing-after", "false-height-source",
                      "missing-before", "unknown-before", "child-future", "wrong-cell", "wrong-cell-world",
                      "wrong-matrix", "bool-result", "malformed-actors", "native-return"):
            with self.subTest(fault=fault):
                spawn, snapshot = surface_fixture()
                h = spawn["jumpReceipts"][0]["landingHeight"]
                cell = h["loadedTerrain"]["cell"]
                if fault == "missing": del spawn["jumpReceipts"][0]["landingHeight"]
                elif fault == "failed": h["heightRefresh"]["returnValue"] = 0
                elif fault == "ignored": h["heightRefresh"]["positionBefore"]["flags"] |= 1 << 23
                elif fault == "point": h["target"][0] += 1
                elif fault == "object": h["heightRefresh"]["objectPointer"] += 4
                elif fault == "world": h["worldContext"]["fieldEpoch"] += 1
                elif fault == "pid": h["preparedEncounter"]["personality"] += 1
                elif fault == "height": h["positionAfter"]["pos_y"] += 4096
                elif fault == "terminal-object": snapshot["actors"][0]["engineIdentity"]["pointer"] += 4
                elif fault == "terminal-world": snapshot["context"]["fieldEpoch"] += 1
                elif fault == "terminal-pid": snapshot["actors"][0]["subjectIdentity"] += 1
                elif fault == "moving": snapshot["actors"][0]["motionPhase"] = "MOVING"
                elif fault == "unloaded": h["loadedTerrain"] = {"status": "unknown", "cell": None}
                elif fault == "collision": cell.update(attribute=0x8002, collision=True); cell["provenance"]["rawWord"] = 0x8002
                elif fault == "raw-word": cell["provenance"]["rawWord"] = 3
                elif fault == "source": cell.update(attribute=16, behavior=16); cell["provenance"]["rawWord"] = 16
                elif fault == "future": h["returnActorFrame"] = snapshot["actorFrame"] + 1
                elif fault == "missing-after": del h["engineIdentityAfter"]
                elif fault == "false-height-source": h["heightSource"] = "unknown"
                elif fault == "missing-before": del h["loadedTerrainBefore"]
                elif fault == "unknown-before": h["loadedTerrainBefore"] = {"status": "unknown", "cell": None}
                elif fault == "child-future": h["heightRefresh"]["returned"] = {"actorFrame": 99, "nativeCycle": 198}
                elif fault == "wrong-cell": cell["x"] += 1
                elif fault == "wrong-cell-world": cell["provenance"]["fieldPointer"] += 4
                elif fault == "wrong-matrix": cell["matrix_index"] += 1
                elif fault == "bool-result": h["heightRefresh"]["returnValue"] = True
                elif fault == "malformed-actors": snapshot["actors"] = [None]
                elif fault == "native-return": h["returnValue"] = 1
                with self.assertRaises(ValueError): check(spawn, snapshot)

    def test_surf_origin_is_not_land_only(self):
        spawn, snapshot = surface_fixture()
        h = spawn["jumpReceipts"][0]["landingHeight"]
        spawn["terrain"] = spawn["finalization"]["receipt"]["terrain"] = 1
        profile = spawn["finalization"]["receipt"]["resolverReceipts"][-1]
        raw = bytearray.fromhex(profile["requestHex"]); raw[9] = 1; profile["requestHex"] = raw.hex()
        cell = h["loadedTerrain"]["cell"]
        cell.update(attribute=16, behavior=16); cell["provenance"]["rawWord"] = 16
        h["loadedTerrainBefore"]["cell"] = deepcopy(cell)
        self.assertTrue(check(spawn, snapshot)["passed"])
        cell.update(attribute=2, behavior=2); cell["provenance"]["rawWord"] = 2
        with self.assertRaises(ValueError): check(spawn, snapshot)

    def test_all_authored_surfaces_rejected_even_native_ground_id(self):
        for surface_type in range(5):
            for surface_id in (4, 0xFFFF):
                spawn, snapshot = surface_fixture()
                h = spawn["jumpReceipts"][0]["landingHeight"]
                hit = {"height": 0, "surfaceId": surface_id, "surfaceType": surface_type, "nodeId": 0,
                       "rawHex": struct.pack("<iHBB", 0, surface_id, surface_type, 0).hex()}
                h["surfaceQuery"].update(returnValue=1, hit=hit)
                with self.subTest(surface=surface_type, id=surface_id), self.assertRaises(ValueError):
                    check(spawn, snapshot)

    def test_constants_have_independent_source_anchors(self):
        root = Path(__file__).resolve().parents[2]
        header = (root / "include/overworld_wild_behavior_data.h").read_text()
        self.assertIn("OW_WILD_SPAWN_TERRAIN_LAND,\n    OW_WILD_SPAWN_TERRAIN_SURF,", header)
        for name, value in (("ROOFTOP", 0), ("SIGNPOST", 1), ("MAILBOX", 2), ("FLOWERBED", 3), ("CANOPY", 4)):
            self.assertRegex(header, rf"OW_WILD_SURFACE_TYPE_{name}\s+{value}")
        self.assertIn("OW_WILD_SURFACE_ID_NATIVE_CANOPY 0xFFFE", header)
        reference = root / ".codex-reference/pokeheartgold"
        if not reference.exists(): self.skipTest("validated local vanilla reference unavailable")
        flags = (reference / "include/map_object.h").read_text()
        self.assertIn("MAPOBJECTFLAG_IGNORE_HEIGHTS = (1 << 23)", flags)
        terrain = (reference / "asm/unk_02054648.s").read_text()
        self.assertIn("asr r0, r0, #0xf", terrain)
        refresh = (reference / "asm/unk_0205FD20.s").read_text().split("sub_02061070: ;", 1)[1].split("thumb_func_end sub_02061070", 1)[0]
        self.assertIn("bl MapObject_CheckIgnoreHeights", refresh)
        self.assertIn("bl MapObject_SetPositionVector", refresh)
        # The native decoder's eight-byte hit must stay anchored to the public
        # C layout, rather than just packing the same invented fixture twice.
        hit = header.split("typedef struct OverworldWildSurfaceHit", 1)[1].split("}", 1)[0]
        self.assertRegex(hit, r"s32\s+height;")
        self.assertRegex(hit, r"u16\s+surfaceId;")
        self.assertRegex(hit, r"u8\s+surfaceType;")
        self.assertRegex(hit, r"u8\s+nodeId;")
