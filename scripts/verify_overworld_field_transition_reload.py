#!/usr/bin/env python3
"""Run the actual field transition driver against the actual resident model.

Only engine adapters are stubbed. Reload clears overlay-local state, never the
resident Actor receipt or context. This host check does not prove live gameplay.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    match = re.search(r"^static [^\n]+ " + name + r"\(", source, re.M)
    if match is None:
        raise ValueError("missing field function: " + name)
    start = source.index("{", match.start())
    depth = 1
    end = start + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[match.start():end]


def harness():
    source = (ROOT / "src/field/map_teleport.c").read_text()
    public = (ROOT / "include/map_teleport.h").read_text()
    internal = (ROOT / "include/overworld_actor_system_internal.h").read_text()
    runtime = source[source.index("typedef struct OverworldFieldTransitionRuntime {"):
                     source.index("static OverworldFieldTerrainStreamRuntime")]
    result_enum = re.search(r"typedef enum OverworldFieldMapHeaderChangeResult \{.*?"
                            r"\} OverworldFieldMapHeaderChangeResult;", public, re.S).group()
    context = internal[internal.index("typedef u32 OverworldActorFieldContext;"):
                       internal.index("typedef OverworldActorFieldContext (*")]
    # The counter is deliberately optional: the regression survives its removal.
    resets = "\n".join(name + " = 0;" for name in re.findall(r"static u32 (\w+);", runtime))
    return r'''
#include <stdio.h>
#include <string.h>
#include "overworld_actor_transition_model.h"
typedef int BOOL;
#define TRUE 1
#define FALSE 0
typedef struct { void *objects; } MapObjectMan;
typedef struct { u16 mapId; } Location;
typedef struct { Location *location; void *playerAvatar; MapObjectMan *mapObjectMan; } FieldSystem;
typedef struct { u16 mapId; MapObjectMan *mapObjectMan; void *mapObjects; } OverworldWildSpawnState;
''' + context + result_enum + runtime + r'''
static BOOL sOverworldWildPlayerFrameServiceActive;
static OverworldActorTransitionState actor;
static u32 residentContext;
static OverworldActorTransitionCall lastCall;
static int failWorkOnce, failed, advanceCount;
static u16 lastReason;
static u32 getContext(void) { return residentContext; }
static OverworldActorResult transition(OverworldActorTransitionCall *call) {
    u8 effects;
    OverworldActorResult result = OverworldActorTransition_Apply(
        &actor, call, residentContext, 3, 1, &effects);
    lastReason = call->reason;
    if (effects & OVERWORLD_ACTOR_TRANSITION_EFFECT_ADVANCE_FIELD) {
        residentContext = call->nextFieldEpoch | ((u32)call->nextMapGeneration << 16);
        advanceCount++;
    }
    lastCall = *call;
    return result;
}
static struct {
    u32 (*getContext)(void);
    OverworldActorResult (*transition)(OverworldActorTransitionCall *);
} compat = {getContext, transition};
#define OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY (&compat)
static BOOL OverworldFieldService_EnsureTransitionAdapters(void) { return TRUE; }
static BOOL OverworldFieldService_IsEnabledMap(u16 map) { (void)map; return TRUE; }
static BOOL OverworldFieldService_ApplyTransitionWork(
    FieldSystem *field, OverworldWildSpawnState *state,
    const OverworldActorTransitionCall *call) {
    (void)field; (void)state; (void)call;
    if (failWorkOnce) { failWorkOnce = 0; return FALSE; }
    return TRUE;
}
''' + function(source, "OverworldFieldService_AcknowledgementForWork") + "\n" + function(
        source, "OverworldFieldService_OnMapHeaderChangedImpl") + r'''
static void reload(void) {
    memset(&sOverworldFieldTransition, 0, sizeof(sOverworldFieldTransition));
    sOverworldWildPlayerFrameServiceActive = FALSE;
''' + resets + r'''
}
static void check(int ok, const char *label) {
    if (!ok) {
        fprintf(stderr, "FAIL %s: driver sequence=%u active=%u; Actor sequence=%u phase=%u maps=%u->%u context=%08x reason=%u\n",
            label, sOverworldFieldTransition.sequence, sOverworldFieldTransition.active,
            actor.sequence, actor.phase, actor.previousMapId, actor.currentMapId,
            residentContext, lastReason);
        failed++;
    }
}
static void fresh(u32 context) {
    reload(); OverworldActorTransition_Reset(&actor);
    residentContext = context; failWorkOnce = 0; advanceCount = 0;
}
static int move(u16 previous, u16 current, int retry) {
    int object;
    MapObjectMan manager = {&object};
    Location location = {current};
    FieldSystem field = {&location, &object, &manager};
    OverworldWildSpawnState wild = {previous, &manager, &object};
    OverworldFieldMapHeaderChangeResult result;
    failWorkOnce = retry;
    result = OverworldFieldService_OnMapHeaderChangedImpl(&field, &wild, previous, current);
    if (retry) {
        u32 sequence = sOverworldFieldTransition.sequence;
        check(result == OVERWORLD_FIELD_MAP_HEADER_CHANGE_UNAVAILABLE
            && sOverworldFieldTransition.active, "failed work keeps retry receipt");
        result = OverworldFieldService_OnMapHeaderChangedImpl(&field, &wild, previous, current);
        check(actor.sequence == sequence, "retry preserves sequence");
    }
    return result == OVERWORLD_FIELD_MAP_HEADER_CHANGE_PRESERVED
        && !sOverworldFieldTransition.active
        && actor.phase == OVERWORLD_ACTOR_TRANSITION_PHASE_COMPLETE;
}
int main(void) {
    int before;
    u32 context;
    OverworldActorTransitionCall completed;
    fresh(0x00010001);
    check(move(33, 67, 1), "first transition with retry completes");
    check(advanceCount == 1 && residentContext == 0x00020002,
        "retry advances resident context exactly once");
    completed = lastCall; context = residentContext; before = advanceCount;
    check(transition(&completed) == OVERWORLD_ACTOR_RESULT_OK
        && completed.work == OVERWORLD_ACTOR_TRANSITION_WORK_COMPLETE
        && residentContext == context && advanceCount == before,
        "completed receipt retry is idempotent");
    reload();
    check(move(67, 69, 0), "overlay reload 67->69 completes");
    check(residentContext == 0x00030003, "second transition advances context");
    fresh(0xFFFEFFFE);
    check(move(33, 67, 0), "pre-wrap transition completes");
    check(residentContext == 0xFFFFFFFF, "pre-wrap context is exact");
    reload();
    check(move(67, 69, 0), "wrap transition completes after reload");
    check(residentContext == 0x00010001, "16-bit generations wrap and skip zero");
    reload();
    check(move(69, 67, 1), "post-wrap transition with retry completes");
    check(residentContext == 0x00020002, "post-wrap context is exact");
    if (failed) return 1;
    puts("field transition reload, retry and context-wrap checks passed");
    return 0;
}
'''


def main():
    with tempfile.TemporaryDirectory(prefix="field-transition-reload-") as temporary:
        directory = Path(temporary)
        source = directory / "harness.c"
        source.write_text(harness())
        binary = directory / "check"
        subprocess.run([os.environ.get("CC", "cc"), "-std=c99", "-Wall", "-Wextra", "-Werror",
            "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-I", str(ROOT / "include"), str(source),
            str(ROOT / "lib/overworld/overworld_actor_transition_model.c"), "-o", str(binary)], check=True)
        return subprocess.run([str(binary)]).returncode


if __name__ == "__main__":
    raise SystemExit(main())
