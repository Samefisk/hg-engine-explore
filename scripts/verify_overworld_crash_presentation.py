#!/usr/bin/env python3
"""Actual-C crash presentation lifecycle check. No ROM or gameplay proof."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from verify_overworld_rebind_pass_through import block

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


def production():
    source = SOURCE.read_text()
    header = (ROOT / "include/overworld_wild_spawns_internal.h").read_text()
    names = ("OW_WILD_SPAWNER_FX32_ONE", "OW_WILD_SPAWNER_MOVEMENT_CRASH_SHAKE_FRAMES",
             "OW_WILD_SPAWNER_WALK_CRASH_SHAKE_FRAMES", "OW_WILD_SPAWNER_MOVEMENT_CRASH_SHAKE_FX32_AMPLITUDE",
             "OW_WILD_LAND_SURF_MAX_SPAWNS", "OW_WILD_HEADBUTT_MAX_SPAWNS", "OW_WILD_FISH_MAX_SPAWNS",
             "OW_WILD_HEADBUTT_SLOT_START", "OW_WILD_FISH_SLOT_START", "OW_WILD_FOLLOWER_SLOT", "OW_WILD_MAX_SPAWNS")
    joined = (source + "\n" + header).replace("\\\n", "")
    constants = []
    for name in names:
        matches = re.findall(r"^#define " + name + r"\s+[^\n]+$", joined, re.M)
        if len(matches) != 1:
            raise ValueError("missing/duplicate source constant " + name)
        constants += matches
    functions = [block(source, marker) for marker in (
        "static s32 OverworldWildSpawns_GetMovementCrashShakeOffset(u8 timer)",
        "static void OverworldWildSpawns_RestoreMovementCrashShake(OverworldWildSpawnState *state, int slot)",
        "static void OverworldWildSpawns_StartMovementCrashShake(\n",
        "static void OverworldWildSpawns_TickMovementCrashShake(OverworldWildSpawnState *state, FieldSystem *fieldSystem)")]
    return "\n".join(constants + functions)


PRELUDE = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32; typedef int32_t s32; typedef uint8_t u8;
typedef struct { u32 posVec[3]; } LocalMapObject;
typedef struct { int active; LocalMapObject *object; } Spawn;
typedef struct { int unused; } FieldSystem;
typedef struct { Spawn spawns[10]; u8 movementCrashShakeTimers[10];
    u32 movementCrashShakeBaseX[10],movementCrashShakeBaseZ[10]; } OverworldWildSpawnState;
static int current=1;
static int OverworldWildSpawns_IsCurrentSpawnObject(FieldSystem *f, Spawn *s)
{ (void)f; return current && s->active && s->object; }
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"crash lifecycle line %d: %s\n",__LINE__,#x); return 1; } } while(0)
'''

MAIN = r'''
int main(void) {
    /* Independent literal contract table, not a copy of the source formula. */
    const int offsets[11]={256,-512,512,-256,256,-512,512,-256,256,-512,0};
    OverworldWildSpawnState s={0}; LocalMapObject o={{38174720,65536,26050560}}, other={{10,20,30}};
    FieldSystem field={0}; const int slot=OW_WILD_FOLLOWER_SLOT;
    s.spawns[slot]=(Spawn){1,&o}; s.spawns[0]=(Spawn){1,&other};
    CHECK(OW_WILD_SPAWNER_WALK_CRASH_SHAKE_FRAMES==11);
    OverworldWildSpawns_StartMovementCrashShake(&s,slot,&o,OW_WILD_SPAWNER_WALK_CRASH_SHAKE_FRAMES);
    CHECK(s.movementCrashShakeTimers[slot]==11);
    for(int i=0;i<11;i++) {
        OverworldWildSpawns_TickMovementCrashShake(&s,&field);
        CHECK(s.movementCrashShakeTimers[slot]==10-i);
        CHECK((s32)o.posVec[0]==38174720+offsets[i]);
        CHECK((s32)o.posVec[2]==26050560-offsets[i]);
        CHECK(o.posVec[1]==65536 && other.posVec[0]==10 && other.posVec[2]==30);
        CHECK(s.movementCrashShakeBaseX[slot]==38174720 && s.movementCrashShakeBaseZ[slot]==26050560);
    }
    OverworldWildSpawns_TickMovementCrashShake(&s,&field);
    CHECK(o.posVec[0]==38174720 && o.posVec[2]==26050560);
    OverworldWildSpawns_StartMovementCrashShake(&s,slot,&o,11);
    OverworldWildSpawns_TickMovementCrashShake(&s,&field);
    OverworldWildSpawns_StartMovementCrashShake(&s,slot,&o,11);
    CHECK(o.posVec[0]==38174720 && o.posVec[2]==26050560);
    CHECK(s.movementCrashShakeBaseX[slot]==38174720 && s.movementCrashShakeTimers[slot]==11);
    current=0;
    OverworldWildSpawns_TickMovementCrashShake(&s,&field);
    CHECK(s.movementCrashShakeTimers[slot]==0 && o.posVec[0]==38174720);
    OverworldWildSpawns_StartMovementCrashShake(NULL,slot,&o,11);
    OverworldWildSpawns_StartMovementCrashShake(&s,-1,&o,11);
    OverworldWildSpawns_StartMovementCrashShake(&s,OW_WILD_MAX_SPAWNS,&o,11);
    OverworldWildSpawns_StartMovementCrashShake(&s,slot,NULL,11);
    CHECK(s.movementCrashShakeTimers[slot]==0);
    puts("PASS actual crash presentation: 11 ticks, restore, restart and ownership");
    return 0;
}
'''


def verify():
    compiler = shutil.which("cc")
    if compiler is None:
        raise RuntimeError("host C compiler unavailable")
    actual = production()
    mutations = {
        "offset": (">> ((timer & 2) >> 1)", ">> 2"),
        "sign": ("state->movementCrashShakeBaseZ[i] - offset", "state->movementCrashShakeBaseZ[i] + offset"),
        "timer": ("state->movementCrashShakeTimers[i]--;", "state->movementCrashShakeTimers[i] -= 2;"),
    }
    variants = {"actual": actual}
    for name, (before, after) in mutations.items():
        if before not in actual:
            raise ValueError("mutation boundary absent: " + name)
        variants[name] = actual.replace(before, after, 1)
    with tempfile.TemporaryDirectory(prefix="ow-crash-presentation-") as directory:
        for name, body in variants.items():
            source, binary = Path(directory) / (name + ".c"), Path(directory) / name
            source.write_text(PRELUDE + body + MAIN)
            subprocess.run([compiler,"-std=c99","-Wall","-Wextra","-Werror",str(source),"-o",str(binary)],
                           check=True,capture_output=True,text=True,timeout=20)
            result = subprocess.run([str(binary)],capture_output=True,text=True,timeout=5)
            if (result.returncode == 0) != (name == "actual"):
                raise AssertionError(name + ": " + result.stdout + result.stderr)
            if name == "actual": print(result.stdout.strip())
    print("PASS mutation controls: offset, sign, timer")


if __name__ == "__main__":
    verify()
