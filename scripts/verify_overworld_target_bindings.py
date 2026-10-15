#!/usr/bin/env python3
"""Check the production Trigger/Cargo value module, without runtime hooks.

The real condition evaluator supplies admitted entries. These host checks do
not prove cargo claims, pickup reachability, role composition, or game motion.
"""

from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "overworld_target_bindings.h"

#define TRIGGER OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST
#define CARGO OVERWORLD_TARGET_BINDING_CARGO
#define OK OVERWORLD_TARGET_BINDING_OK
#define UNTIL_CLEAR OVERWORLD_TARGET_BINDING_UNTIL_CLEAR
#define FRAMES OVERWORLD_TARGET_BINDING_FRAMES

static OverworldActorHandle handle(u16 slot)
{
    return (OverworldActorHandle){.slot=slot, .generation=11,
        .fieldEpoch=12, .mapGeneration=13, .encounterGeneration=14};
}

static OverworldBehaviorConditionWorldView world(void)
{
    OverworldBehaviorConditionWorldView w = {0};
    w.subject = handle(0);
    w.frame = 100;
    w.playerValid = 1;
    w.playerX = 8;
    w.playerY = 9;
    w.actorCount = 3;
    for (unsigned i=0; i<3; ++i) {
        w.actors[i].actor = handle((u16)i);
        w.actors[i].valid = 1;
        w.actors[i].x = (s16)(i+1);
        w.actors[i].y = 1;
    }
    return w;
}

static OverworldBehaviorConditionEntryResult entry(u16 slot)
{
    OverworldBehaviorConditionEntryResult r = {0};
    r.target.kind = OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;
    r.target.actor = handle(slot);
    r.conditionId = 123;
    r.applicationIndex = 19;
    r.active = r.triggered = r.conditionTrue = 1;
    return r;
}

static OverworldActorHandle changed(OverworldActorHandle h, unsigned field)
{
    switch (field) {
    case 0: ++h.slot; break;
    case 1: ++h.generation; break;
    case 2: ++h.fieldEpoch; break;
    case 3: ++h.mapGeneration; break;
    case 4: ++h.encounterGeneration; break;
    default: assert(0);
    }
    return h;
}

static void admitted_entry_before_reduction(void)
{
    OverworldBehaviorConditionWorldView w = world();
    OverworldTargetBindingsState b;
    OverworldBehaviorConditionDefinition d[2] = {0};
    OverworldBehaviorConditionEntryInput in[2] = {0};
    OverworldBehaviorConditionEntryState s[2] = {0};
    OverworldBehaviorConditionEntryResult exact[2];
    OverworldBehaviorConditionResult reduced;
    OverworldTargetBindingPosition p;
    for (unsigned i=0; i<2; ++i) {
        d[i].conditionId = (u16)(100+i);
        d[i].applicationIndex = 19;
        d[i].kind = OVERWORLD_BEHAVIOR_CONDITION_POKEMON_NOTICED;
        d[i].activationMode = OVERWORLD_BEHAVIOR_CONDITION_WHILE_TRUE;
        d[i].targetKind = OVERWORLD_BEHAVIOR_CONDITION_TARGET_MATCHED_ACTOR;
        d[i].rangeKind = OVERWORLD_BEHAVIOR_CONDITION_RANGE_RADIUS;
        d[i].distance = 8;
        d[i].chance = 100;
        in[i].eligibleActorMask = (u16)(1u << (i+1));
    }
    assert(OverworldTargetBindings_Init(&b,&w.subject)==OK);
    /* Capture the exact first entry at its admission boundary. */
    assert(OverworldBehaviorCondition_EvaluateEntry(&d[0],&in[0],&w,
        &s[0],&exact[0])==OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(exact[0].active && exact[0].triggered && exact[0].conditionTrue);
    assert(OverworldTargetBindings_CaptureEntry(&b,&w,&w.subject,&exact[0],
        TRIGGER,UNTIL_CLEAR,0)==OK);
    memset(s,0,sizeof(s));
    /* The real same-application reduction chooses the later actor. */
    assert(OverworldBehaviorCondition_EvaluateWithResults(d,in,s,2,&w,
        &reduced,exact)==OVERWORLD_BEHAVIOR_CONDITION_OK);
    assert(exact[0].target.actor.slot==1 && exact[1].target.actor.slot==2);
    assert(reduced.resolvedTarget.actor.slot==2);
    assert(OverworldTargetBindings_Resolve(&b,&w,TRIGGER,&p)==OK);
    assert(p.target.actor.slot==1 && b.bindings[TRIGGER].sourceConditionId==100);
    assert(OverworldTargetBindings_CaptureEntry(&b,&w,&w.subject,&exact[1],
        TRIGGER,UNTIL_CLEAR,0)==OVERWORLD_TARGET_BINDING_ALREADY_BOUND);
}

static void admission_and_owner(void)
{
    OverworldBehaviorConditionWorldView w = world();
    OverworldTargetBindingsState b, before;
    OverworldBehaviorConditionEntryResult r = entry(1), bad;
    OverworldTargetBindingPosition p;
    assert(OverworldTargetBindings_Init(&b,&w.subject)==OK);
    for (unsigned field=0; field<3; ++field) {
        for (u8 value=0; value<3; value+=2) {
            bad=r;
            if (field==0) bad.active=value;
            if (field==1) bad.triggered=value;
            if (field==2) bad.conditionTrue=value;
            assert(OverworldTargetBindings_CaptureEntry(&b,&w,&w.subject,&bad,
                TRIGGER,UNTIL_CLEAR,0)==OVERWORLD_TARGET_BINDING_NOT_ADMITTED);
            assert(!(b.bindings[TRIGGER].flags & OVERWORLD_TARGET_BINDING_BOUND));
        }
    }
    for (unsigned field=0; field<5; ++field) {
        OverworldActorHandle stale=changed(w.subject,field);
        OverworldBehaviorConditionWorldView wrong=w;
        before=b;
        assert(OverworldTargetBindings_CaptureEntry(&b,&w,&stale,&r,
            TRIGGER,UNTIL_CLEAR,0)==OVERWORLD_TARGET_BINDING_STALE_SUBJECT);
        assert(memcmp(&b,&before,sizeof(b))==0);
        wrong.subject=stale;
        memset(&p,0xAA,sizeof(p));
        assert(OverworldTargetBindings_Resolve(&b,&wrong,TRIGGER,&p)
            ==OVERWORLD_TARGET_BINDING_STALE_SUBJECT);
        assert(p.target.kind==0 && p.x==0 && p.y==0);
        before=b;
        assert(OverworldTargetBindings_ClearAll(&b,&stale,
            OVERWORLD_TARGET_BINDING_CLEAR_CONTEXT)==OVERWORLD_TARGET_BINDING_STALE_SUBJECT);
        assert(memcmp(&b,&before,sizeof(b))==0);
    }
    for (unsigned field=1; field<5; ++field) {
        OverworldActorHandle invalid=w.subject;
        if (field==1) invalid.generation=0;
        if (field==2) invalid.fieldEpoch=0;
        if (field==3) invalid.mapGeneration=0;
        if (field==4) invalid.encounterGeneration=0;
        assert(OverworldTargetBindings_Init(&b,&invalid)
            ==OVERWORLD_TARGET_BINDING_INVALID_ARGUMENT);
    }
}

static void current_position_fixed_identity(void)
{
    OverworldBehaviorConditionWorldView w = world(), wrong;
    OverworldTargetBindingsState b;
    OverworldBehaviorConditionEntryResult r = entry(1), replacement=entry(2);
    OverworldTargetBindingPosition p;
    assert(OverworldTargetBindings_Init(&b,&w.subject)==OK);
    assert(OverworldTargetBindings_CaptureEntry(&b,&w,&w.subject,&r,
        CARGO,UNTIL_CLEAR,0)==OK);
    w.actors[1].x=27;
    w.actors[1].y=-8;
    assert(OverworldTargetBindings_Resolve(&b,&w,CARGO,&p)==OK);
    assert(p.x==27 && p.y==-8 && p.target.actor.slot==1);
    for (unsigned field=0; field<5; ++field) {
        wrong=w;
        wrong.actors[1].actor=changed(r.target.actor,field);
        memset(&p,0xAA,sizeof(p));
        assert(OverworldTargetBindings_Resolve(&b,&wrong,CARGO,&p)
            ==OVERWORLD_TARGET_BINDING_STALE_TARGET);
        assert(p.target.kind==0 && p.x==0 && p.y==0);
        assert(b.bindings[CARGO].target.actor.slot==1);
        assert(OverworldTargetBindings_CaptureEntry(&b,&wrong,&wrong.subject,
            &replacement,CARGO,UNTIL_CLEAR,0)==OVERWORLD_TARGET_BINDING_ALREADY_BOUND);
    }
    wrong=w;
    wrong.actors[1].valid=0;
    assert(OverworldTargetBindings_Resolve(&b,&wrong,CARGO,&p)
        ==OVERWORLD_TARGET_BINDING_STALE_TARGET);
    wrong=w;
    wrong.actors[2]=wrong.actors[1];
    assert(OverworldTargetBindings_Resolve(&b,&wrong,CARGO,&p)
        ==OVERWORLD_TARGET_BINDING_STALE_TARGET);
    assert(OverworldTargetBindings_Clear(&b,&w.subject,CARGO,
        OVERWORLD_TARGET_BINDING_CLEAR_DESPAWN)==OK);
    assert(b.bindings[CARGO].reason==OVERWORLD_TARGET_BINDING_CLEAR_DESPAWN);
    assert(OverworldTargetBindings_Resolve(&b,&w,CARGO,&p)==OVERWORLD_TARGET_BINDING_EMPTY);
    assert(OverworldTargetBindings_CaptureEntry(&b,&w,&w.subject,&replacement,
        CARGO,UNTIL_CLEAR,0)==OK);
    assert(OverworldTargetBindings_Resolve(&b,&w,CARGO,&p)==OK && p.target.actor.slot==2);
}

static void conflicts_player_and_clear(void)
{
    OverworldBehaviorConditionWorldView w=world();
    OverworldTargetBindingsState b;
    OverworldBehaviorConditionEntryResult self=entry(0), r=entry(1), cargo=entry(2);
    OverworldTargetBindingPosition p;
    assert(OverworldTargetBindings_Init(&b,&w.subject)==OK);
    for (u8 name=0; name<OVERWORLD_TARGET_BINDING_COUNT; ++name) {
        assert(OverworldTargetBindings_CaptureEntry(&b,&w,&w.subject,&self,
            name,UNTIL_CLEAR,0)==OVERWORLD_TARGET_BINDING_CONFLICT);
    }
    assert(OverworldTargetBindings_CaptureEntry(&b,&w,&w.subject,&r,
        TRIGGER,UNTIL_CLEAR,0)==OK);
    assert(OverworldTargetBindings_CaptureEntry(&b,&w,&w.subject,&r,
        CARGO,UNTIL_CLEAR,0)==OK);
    assert(OverworldTargetBindings_Resolve(&b,&w,CARGO,&p)==OK
        && p.target.actor.slot==r.target.actor.slot);
    assert(OverworldTargetBindings_ClearAll(&b,&w.subject,
        OVERWORLD_TARGET_BINDING_CLEAR_ABORT)==OK);
    assert(OverworldTargetBindings_CaptureEntry(&b,&w,&w.subject,&r,
        CARGO,UNTIL_CLEAR,0)==OK);
    assert(OverworldTargetBindings_CaptureEntry(&b,&w,&w.subject,&r,
        TRIGGER,UNTIL_CLEAR,0)==OK);
    assert(OverworldTargetBindings_Resolve(&b,&w,TRIGGER,&p)==OK
        && p.target.actor.slot==r.target.actor.slot);
    assert(OverworldTargetBindings_ClearAll(&b,&w.subject,
        OVERWORLD_TARGET_BINDING_CLEAR_COMPLETE)==OK);
    r.target.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER;
    memset(&r.target.actor,0,sizeof(r.target.actor));
    assert(OverworldTargetBindings_CaptureEntry(&b,&w,&w.subject,&r,
        CARGO,UNTIL_CLEAR,0)==OVERWORLD_TARGET_BINDING_INVALID_ARGUMENT);
    assert(OverworldTargetBindings_CaptureEntry(&b,&w,&w.subject,&r,
        TRIGGER,UNTIL_CLEAR,0)==OK);
    assert(OverworldTargetBindings_CaptureEntry(&b,&w,&w.subject,&cargo,
        CARGO,UNTIL_CLEAR,0)==OK);
    w.playerX=-3;
    w.playerY=21;
    assert(OverworldTargetBindings_Resolve(&b,&w,TRIGGER,&p)==OK && p.x==-3 && p.y==21);
    w.playerValid=0;
    assert(OverworldTargetBindings_Resolve(&b,&w,TRIGGER,&p)
        ==OVERWORLD_TARGET_BINDING_STALE_TARGET);
    assert(b.bindings[TRIGGER].target.kind==OVERWORLD_BEHAVIOR_TARGET_REFERENCE_PLAYER);
    assert(OverworldTargetBindings_Resolve(&b,&w,CARGO,&p)==OK);
    assert(OverworldTargetBindings_ClearAll(&b,&w.subject,
        OVERWORLD_TARGET_BINDING_CLEAR_ROLE)==OK);
    assert(b.bindings[TRIGGER].flags==0 && b.bindings[CARGO].flags==0);
    assert(OverworldTargetBindings_Init(&b,&b.subject)==OK);
    assert(b.subject.generation==11 && b.subject.encounterGeneration==14);
}

static void expiry_and_wrap(void)
{
    OverworldBehaviorConditionWorldView w=world();
    OverworldTargetBindingsState b;
    OverworldBehaviorConditionEntryResult r=entry(1), next=entry(2);
    OverworldTargetBindingPosition p;
    assert(OverworldTargetBindings_Init(&b,&w.subject)==OK);
    assert(OverworldTargetBindings_CaptureEntry(&b,&w,&w.subject,&r,
        TRIGGER,FRAMES,0)==OVERWORLD_TARGET_BINDING_INVALID_ARGUMENT);
    assert(OverworldTargetBindings_CaptureEntry(&b,&w,&w.subject,&r,
        TRIGGER,UNTIL_CLEAR,1)==OVERWORLD_TARGET_BINDING_INVALID_ARGUMENT);
    w.frame=UINT32_MAX-2;
    assert(OverworldTargetBindings_CaptureEntry(&b,&w,&w.subject,&r,
        TRIGGER,FRAMES,5)==OK);
    assert(b.bindings[TRIGGER].expiresAt==2);
    const u32 live[]={UINT32_MAX-2,UINT32_MAX,0,1};
    for (unsigned i=0; i<sizeof(live)/sizeof(live[0]); ++i) {
        w.frame=live[i];
        assert(OverworldTargetBindings_Resolve(&b,&w,TRIGGER,&p)==OK);
    }
    w.frame=2;
    memset(&p,0xAA,sizeof(p));
    assert(OverworldTargetBindings_Resolve(&b,&w,TRIGGER,&p)==OVERWORLD_TARGET_BINDING_EXPIRED);
    assert(p.target.kind==0 && p.x==0 && p.y==0);
    assert(b.bindings[TRIGGER].target.actor.slot==1 && b.bindings[TRIGGER].expiresAt==2);
    assert(OverworldTargetBindings_CaptureEntry(&b,&w,&w.subject,&next,
        TRIGGER,FRAMES,5)==OVERWORLD_TARGET_BINDING_ALREADY_BOUND);
    assert(OverworldTargetBindings_Clear(&b,&w.subject,TRIGGER,
        OVERWORLD_TARGET_BINDING_CLEAR_EXPLICIT)==OK);
    assert(OverworldTargetBindings_CaptureEntry(&b,&w,&w.subject,&next,
        TRIGGER,UNTIL_CLEAR,0)==OK);
    w.frame+=UINT16_MAX;
    assert(OverworldTargetBindings_Resolve(&b,&w,TRIGGER,&p)==OK && p.target.actor.slot==2);
}

int main(void)
{
    admitted_entry_before_reduction();
    admission_and_owner();
    current_position_fixed_identity();
    conflicts_player_and_clear();
    expiry_and_wrap();
    puts("production Trigger/Cargo binding checks passed");
    return 0;
}
'''


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="overworld-target-bindings-") as directory:
        source = Path(directory) / "bindings.c"
        executable = Path(directory) / "bindings"
        source.write_text(FIXTURE)
        subprocess.run([
            "cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-DOVERWORLD_BEHAVIOR_HOST",
            "-I", str(ROOT / "include"), str(source),
            str(ROOT / "lib/overworld/overworld_target_bindings.c"),
            str(ROOT / "lib/overworld/overworld_behavior_conditions.c"),
            str(ROOT / "lib/overworld/overworld_vision.c"),
            "-o", str(executable),
        ], check=True, timeout=30)
        subprocess.run([str(executable)], check=True, timeout=30)


if __name__ == "__main__":
    main()
