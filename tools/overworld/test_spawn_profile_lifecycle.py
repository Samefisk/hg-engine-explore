"""S1 production spawn-order regression; no packaged-ROM/gameplay claim."""
from pathlib import Path
import subprocess
import sys
import unittest


class SpawnProfileLifecycleTests(unittest.TestCase):
    def test_actual_native_range_setup_is_unlimited(self):
        from tools.overworld.test_picked_up_actor_control import extract_function
        import tempfile
        root = Path(__file__).resolve().parents[2]
        wild = (root / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
        helper = (root / "src/overworld_wild_helper_overlay/overworld_wild_helper_overlay.c").read_text()
        source = RANGE_PRELUDE + extract_function(wild, "OverworldWildSpawns_ApplyMovementRange", "void")
        source += extract_function(helper, "OverworldWildHelper_CreatePresentationObject", "LocalMapObject *") + RANGE_DRIVER
        with tempfile.TemporaryDirectory(prefix="overworld-native-range-") as temporary:
            directory = Path(temporary); unit = directory / "range.c"; binary = directory / "range"
            unit.write_text(source)
            compiled = subprocess.run(["cc", "-std=gnu11", "-O2", "-Wall", "-Wextra", "-Werror", "-Wno-macro-redefined", str(unit), "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            measured = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(measured.returncode, 0, measured.stdout + measured.stderr)

    def test_actual_spawn_setup_order_and_failure_controls(self):
        root = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, str(root / "scripts/verify_overworld_spawn_profile_lifecycle.py")],
            cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS 32 spawn-order cases", result.stdout)
        self.assertEqual(result.stdout.count("PASS known-bad spawn rejected:"), 6)


RANGE_PRELUDE = '\n#include <assert.h>\n#include <stdint.h>\n#include <string.h>\n#include <stddef.h>\ntypedef int BOOL; typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int32_t s32;\n#define NULL ((void *)0)\n#define OW_WILD_MOVE_STOCK_IDLE 0\n#define OW_WILD_OBJECT_ID_START 160\n#define OVERWORLD_WILD_SPAWNS_BATTLE_SCRIPT 99\n#define OW_WILD_HELPER_PAL_PARAM_ENABLE 4\n#define OW_WILD_HELPER_PAL_PARAM_SHINY 8\n#define BIT_VANISH 1\n#define MAPOBJECTFLAG_UNK8 2\n#define MAPOBJECTFLAG_KEEP 4\ntypedef struct LocalMapObject {s32 xRange,yRange;u32 flags,posVec[3];int facingInit,curFacing,nextFacing,curFacingBak,nextFacingBak,xCurr,yCurr,xInit,yInit,xPrev,yPrev,id,script;}LocalMapObject;\ntypedef struct {u16 species;u8 form,shiny;}OverworldWildSpawn;\ntypedef struct {OverworldWildSpawn spawns[10];}OverworldWildSpawnState;\ntypedef struct {int mapId;}Location;\ntypedef struct {void *mapObjectMan;Location *location;}FieldSystem;\nstatic LocalMapObject object;static BOOL failCreate;static unsigned setX,setY,render;\nstatic void MapObject_SetXRange(LocalMapObject *o,u32 n){o->xRange=(s32)n;setX++;}\nstatic void MapObject_SetYRange(LocalMapObject *o,u32 n){o->yRange=(s32)n;setY++;}\nstatic void MapObject_SetID(LocalMapObject *o,int n){o->id=n;}\nstatic void MapObject_SetScript(LocalMapObject *o,int n){o->script=n;}\nstatic void MapObject_SetCurrentX(LocalMapObject *o,u32 n){o->xCurr=(int)n;}\nstatic void MapObject_SetCurrentY(LocalMapObject *o,u32 n){o->yCurr=(int)n;}\nstatic void OverworldWildCustomMovement_SetFieldSystem(FieldSystem *f){assert(f);}\nstatic u32 Sprite(u16 species,u8 form){assert(species==43 && form==0);return 123;}\nstatic void Render(LocalMapObject *o,u16 species,u8 form,u32 sprite,u8 shiny){assert(o==&object&&species==43&&!form&&sprite==123&&!shiny);render++;}\nstatic const struct {u32(*getSpriteId)(u16,u8);void(*applyRenderParams)(LocalMapObject *,u16,u8,u32,u8);}metadata={Sprite,Render};\n#define OVERWORLD_WILD_SPAWN_METADATA_ENTRY (&metadata)\nstatic LocalMapObject *CreateSpecialFieldObjectWithParams(void *manager,int x,int y,u8 facing,u32 sprite,u8 move,int map,int zero,u8 behavior,int palette){assert(manager&&x==10&&y==20&&facing==3&&sprite==123&&move==0&&map==33&&!zero&&behavior==2&&palette==4);return failCreate?NULL:&object;}\n'
RANGE_DRIVER = '\nint main(void){\n OverworldWildSpawnState state={0};Location location={33};FieldSystem field={&state,&location};state.spawns[0].species=43;\n const u8 values[]={0,32,232,255};\n for(unsigned i=0;i<4;i++){\n  memset(&object,0,sizeof(object));setX=setY=render=0;\n  OverworldWildSpawns_ApplyMovementRange(&object,values[i]);\n  assert(object.xRange==-1&&object.yRange==-1&&setX==1&&setY==1);\n  memset(&object,0,sizeof(object));setX=setY=render=0;\n  assert(OverworldWildHelper_CreatePresentationObject(&field,&state,0,10,20,3,2,values[i])==&object);\n  assert(object.xRange==-1&&object.yRange==-1&&setX==1&&setY==1&&render==1);\n  assert(object.xInit==10&&object.yInit==20&&object.xCurr==10&&object.yCurr==20);\n }\n failCreate=1;setX=setY=render=0;\n assert(!OverworldWildHelper_CreatePresentationObject(&field,&state,0,10,20,3,2,0));assert(!setX&&!setY&&!render);\n return 0;\n}\n'

if __name__ == "__main__":
    unittest.main()
