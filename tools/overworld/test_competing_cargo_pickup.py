"""Actual-C pursuit competition, physical pickup, and claimant cleanup.

Reuse the established Atomic/HELD composition fixture. Engine reads remain
named host seams; reservation, Observe, Atomic, HELD, and abort are production C.
"""
import unittest

from tools.overworld import test_throw_failure_composition as shared


def fixture(entry):
    source = shared.atomic_handoff_fixture().split("int main(void)", 1)[0]
    source = shared.replace(source, "movementCrashShakeTimers[10],movementTeleportVisiblePause[10]",
        "movementCrashShakeTimers[10],movementRamCrashShakeTimers[10],movementTeleportVisiblePause[10]")
    helper = shared.functions(shared.HELPER, [
        ("OverworldWildHelper_IsValidPickupThrowTarget", "BOOL"),
        ("OverworldWildHelper_IsEligiblePickupThrowTarget", "BOOL"),
        ("OverworldWildHelper_ShouldPauseReservedPickupTarget", "BOOL"),
        ("OverworldWildHelper_QueryPickupThrowTarget", "BOOL"),
        ("OverworldWildHelper_TryStartPickupThrowAction", "BOOL"),
    ])
    return source + "\n#define OW_WILD_HELPER_PICKUP_THROW_QUERY_STABLE 1\n" \
        "#define OW_WILD_HELPER_PICKUP_THROW_QUERY_RESERVED_PAUSE 2\n" \
        "#define OW_WILD_SPAWN_ENTRY_HOP 2\n" + helper + DRIVER \
        + f"\nint main(void) {{ {entry}(); return 0; }}\n"


class CompetingCargoPickupTests(unittest.TestCase):
    def check_case(self, entry):
        result = shared.run(fixture(entry), "competing-cargo-" + entry.lower())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_both_pursuers_reserve_and_observe_the_same_unheld_cargo(self):
        self.check_case("Reservations")

    def test_first_physical_pickup_wins_in_both_slot_orders_and_roles(self):
        self.check_case("FirstPickup")

    def test_loser_abort_preserves_the_remaining_and_held_owner(self):
        self.check_case("Cleanup")

    def test_stale_identity_unreached_and_held_cargo_stay_rejected(self):
        self.check_case("InvalidPickup")

    def test_target_disappearance_releases_both_claimants(self):
        self.check_case("TargetGone")

    def test_cleanup_preserves_unrelated_flight_target_mask(self):
        self.check_case("UnrelatedFlight")

    def test_abort_preserves_a_subject_incoming_pursuit_or_holder(self):
        self.check_case("IncomingAbort")

    def test_reciprocal_pursuit_pickup_retires_only_the_cargo_outgoing_claim(self):
        self.check_case("ReciprocalPickup")


DRIVER = r'''
/* Both slot orders, then a Wild/Follower competition with each first. */
static const unsigned pairs[4][2]={{0,1},{1,0},{0,7},{7,0}};
static unsigned other;
static OverworldBehaviorConditionEntryState claimStates[10];
static void Pair(unsigned pair,BOOL claimed) {
    Reset(pairs[pair][0],2);other=pairs[pair][1];
    memset(claimStates,0,sizeof(claimStates));
    objects[other]=objects[carrier];objects[other].xCurr=9;
    objects[other].posVec[0]=9*0x10000+0x8000;
    state.spawns[other]=(OverworldWildSpawn){&objects[other],1,11+other,100+other};
    actors.slots[other].snapshot=(OverworldActorStateSnapshot){.active=1,.handle=Handle(other),
        .subjectIdentity=100+other,.role=other==OW_WILD_FOLLOWER_SLOT
            ?OVERWORLD_ACTOR_ROLE_FOLLOWER:OVERWORLD_ACTOR_ROLE_WILD,
        .motionPhase=OVERWORLD_ACTOR_PHASE_IDLE};
    conditions.actors[other].subject=Handle(other);conditions.actors[other].count=1;
    unsigned index=0;for(;index<blob->header.conditionEntryCount;index++)
        if(blob->conditionOptions[index].captureBinding==2
            &&blob->conditionOptions[index].mustBeReachableForPickup
            &&(blob->conditionOptions[index].subjectRoleMask
                &(other==OW_WILD_FOLLOWER_SLOT?2:1)))break;
    assert(index<blob->header.conditionEntryCount);
    conditions.actors[other].catalogEntryIndexes[0]=index;
    blob->conditionOptions[index].pickupHeight=2;
    conditions.frame.world.actorCount=3;
    conditions.frame.world.actors[2].actor=Handle(other);
    conditions.frame.world.actors[2].valid=1;
    conditions.frame.world.actors[2].x=9;conditions.frame.world.actors[2].y=10;
    assert(OverworldTargetBindings_Init(&conditions.bindings[other],
        &conditions.actors[other].subject)==OVERWORLD_TARGET_BINDING_OK);
    unsigned first=carrier;carrier=other;conditions.frame.world.subject=Handle(other);
    Bind(OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST,TRUE);
    Bind(OVERWORLD_TARGET_BINDING_CARGO,FALSE);
    conditions.bindings[other].bindings[OVERWORLD_TARGET_BINDING_CARGO].sourceConditionId=
        blob->conditionEntries[index].conditionId;
    carrier=first;conditions.frame.world.subject=Handle(first);
    profiles[other]=profiles[carrier];primitiveValues[other]=primitiveValues[carrier];
    for(unsigned i=0;i<2;i++) {
        unsigned slot=i?other:carrier;
        conditions.actors[slot].valid=1;conditions.actors[slot].states=&claimStates[slot];
        conditions.actors[slot].stateCapacity=1;
        claimStates[slot].flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE;
        claimStates[slot].targetKind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;
        claimStates[slot].targetSlot=cargoSlot;
        claimStates[slot].targetGeneration=Handle(cargoSlot).generation;
        claimStates[slot].targetEncounterGeneration=Handle(cargoSlot).encounterGeneration;
    }
    memset(&runtime.throwState,0,sizeof(runtime.throwState));
    if(claimed) {
        runtime.throwState.targets[carrier]=runtime.throwState.targets[other]=
            OW_WILD_HELPER_THROW_TARGET_ENCODE(cargoSlot);
        runtime.throwState.targetMask=1u<<cargoSlot;
        runtime.throwState.carrierMask=(1u<<carrier)|(1u<<other);
    }
}
static void Near(unsigned slot) {
    objects[slot].xCurr=10;objects[slot].posVec[0]=10*0x10000+0x8000;
    for(unsigned i=0;i<conditions.frame.world.actorCount;i++)
        if(conditions.frame.world.actors[i].actor.slot==slot)
            conditions.frame.world.actors[i].x=10;
}
static BOOL Reserve(unsigned slot) {
    return OverworldWildHelper_TryStartPickupThrowAction(&state,&runtime.throwState,
        &runtime.spawnPresentations,slot,cargoSlot,0,0);
}
static OverworldPickupRouteEdgeResult Atomic(unsigned slot,
    const OverworldActorHandle *subject,const OverworldActorHandle *target) {
    OverworldPickupRouteWildWorld world;OverworldWildSpawns_InitRouteWorld(&state,slot,&world);
    return OverworldPickupRouteWild_AtomicPickup(&world,subject,target);
}
static void Reservations(void) {
    for(unsigned pair=0;pair<4;pair++) {
        Pair(pair,FALSE);assert(Reserve(carrier));
        u32 facts=OverworldThrowObservation_Observe(&state,other,&profiles[other],blob,
            &conditions,OverworldWildSpawns_IsCurrentSpawnObject,OverworldWildSpawns_QueryPickupThrowTarget);
        assert(facts&((1u<<cargoSlot)<<8));
        assert(Reserve(other));
        assert(runtime.throwState.targets[carrier]==OW_WILD_HELPER_THROW_TARGET_ENCODE(cargoSlot));
        assert(runtime.throwState.targets[other]==OW_WILD_HELPER_THROW_TARGET_ENCODE(cargoSlot));
        assert(runtime.throwState.targetMask==(1u<<cargoSlot));
        assert(runtime.throwState.carrierMask==((1u<<carrier)|(1u<<other)));
        assert(!pickups && !cancels && state.movementActorControlModes[cargoSlot]==0);
        free(blob);
    }
}
static void FirstPickup(void) {
    for(unsigned pair=0;pair<4;pair++)for(unsigned laterWins=0;laterWins<2;laterWins++)for(unsigned busy=0;busy<2;busy++) {
        Pair(pair,TRUE);unsigned winner=laterWins?other:carrier,loser=laterWins?carrier:other;
        Near(winner);if(laterWins) {objects[loser].xCurr=9;objects[loser].posVec[0]=9*0x10000+0x8000;}
        OverworldActorHandle s=Handle(loser),target=Handle(cargoSlot);
        assert(Atomic(loser,&s,&target)==OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED);
        if(busy) {
            OverworldActorRuntimeSlot *slot=&actors.slots[loser];
            OverworldMotionPlan plan={.version=OVERWORLD_MOTION_MODEL_VERSION,
                .kind=OVERWORLD_MOTION_KIND_WALK,.fieldEpoch=3,.reservationId=99,
                .startX=9,.startY=10,.targetX=10,.targetY=10,
                .startBaseY=65536,.targetBaseY=65536,.duration=16,.distance=1};
            assert(OverworldMotion_Begin(&slot->motion,&plan)==OVERWORLD_MOTION_DECISION_ACCEPTED);
            slot->snapshot.motionPhase=OVERWORLD_ACTOR_PHASE_MOVING;
            slot->snapshot.motionKind=OVERWORLD_MOTION_KIND_WALK;
            slot->snapshot.reservationId=99;slot->snapshot.inputOwnership=1;
            state.movementInProgressMask|=1u<<loser;
            runtime.movementMotionIdentities[loser]=99;
            objects[loser].flags|=MAPOBJECTFLAG_SINGLE_MOVEMENT;
        }
        OverworldActorRuntimeSlot before=actors.slots[loser];
        u16 beforeMotionMask=state.movementInProgressMask;
        u32 beforeFlags=objects[loser].flags;
        carrier=winner;assert(OverworldWildSpawns_StartCarriedThrowTarget(&state,winner,cargoSlot));
        assert(pickups==1 && state.movementActorControlModes[cargoSlot]==OW_WILD_ACTOR_CONTROL_HELD);
        assert(runtime.throwState.targets[winner]==OW_WILD_HELPER_THROW_TARGET_ENCODE_CARRIED(cargoSlot));
        unsigned heldOwners=0;for(unsigned i=0;i<10;i++)
            if((runtime.throwState.targets[i]&0x80)
                &&OW_WILD_HELPER_THROW_TARGET_DECODE(runtime.throwState.targets[i])==cargoSlot)heldOwners++;
        assert(heldOwners==1);
        assert(runtime.throwState.targets[loser]==0 && !(runtime.throwState.carrierMask&(1u<<loser)));
        assert(!conditions.bindings[loser].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST].flags
            && !conditions.bindings[loser].bindings[OVERWORLD_TARGET_BINDING_CARGO].flags);
        assert(!(claimStates[loser].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE));
        assert(memcmp(&before,&actors.slots[loser],sizeof(before))==0
            && state.movementInProgressMask==beforeMotionMask && objects[loser].flags==beforeFlags);
        s=Handle(loser);Near(loser);
        assert(Atomic(loser,&s,&target)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID);
        /* Held actors remain selectable (T50), but cannot gain two holders. */
        assert(Reserve(loser));
        assert(Atomic(loser,&s,&target)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID);
        assert(!OverworldWildSpawns_StartCarriedThrowTarget(&state,loser,cargoSlot));
        assert(pickups==1 && runtime.throwState.targets[winner]
            ==OW_WILD_HELPER_THROW_TARGET_ENCODE_CARRIED(cargoSlot));free(blob);
    }
}
static void Cleanup(void) {
    for(unsigned pair=0;pair<4;pair++)for(unsigned held=0;held<2;held++) {
        Pair(pair,TRUE);unsigned winner=carrier,loser=other;
        if(held)assert(OverworldWildSpawns_StartCarriedThrowTarget(&state,winner,cargoSlot));
        OverworldTargetBindingsState before=conditions.bindings[winner];
        unsigned releases=releaseCalls,contacts=contactCancels;
        OverworldWildSpawns_AbortThrow(&state,loser);
        assert(runtime.throwState.targets[loser]==0 && !(runtime.throwState.carrierMask&(1u<<loser)));
        assert(runtime.throwState.targets[winner]==(OW_WILD_HELPER_THROW_TARGET_ENCODE(cargoSlot)|(held?0x80:0)));
        assert(runtime.throwState.targetMask==(1u<<cargoSlot));
        assert(runtime.throwState.carrierMask==(1u<<winner));
        assert(state.movementActorControlModes[cargoSlot]==(held?OW_WILD_ACTOR_CONTROL_HELD:0));
        assert(!(claimStates[loser].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE)
            && (claimStates[winner].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE));
        assert(releaseCalls==releases && contactCancels==contacts);
        assert(memcmp(&before,&conditions.bindings[winner],sizeof(before))==0);
        OverworldWildSpawns_AbortThrow(&state,winner);
        assert(!runtime.throwState.targetMask && !runtime.throwState.carrierMask);
        assert(state.movementActorControlModes[cargoSlot]==0);
        assert(releaseCalls==releases+(held?1:0));free(blob);
    }
}
static void InvalidPickup(void) {
    for(unsigned fault=0;fault<9;fault++) {
        Pair(0,TRUE);OverworldActorHandle s=Handle(carrier),target=Handle(cargoSlot);
        switch(fault) {
        case 0:s.generation++;break;
        case 1:target.generation++;break;
        case 2:actors.slots[cargoSlot].snapshot.subjectIdentity++;break;
        case 3:state.spawns[cargoSlot].encounterGeneration++;break;
        case 4:state.spawns[cargoSlot].active=0;break;
        case 5:ownerCurrent=FALSE;break;
        case 6:Near(carrier);objects[cargoSlot].posVec[0]+=1;break;
        case 7:state.movementActorControlModes[cargoSlot]=OW_WILD_ACTOR_CONTROL_HELD;break;
        case 8:runtime.throwState.targets[other]|=0x80;break;
        }
        OverworldWildThrowState before=runtime.throwState;
        assert(Atomic(carrier,&s,&target)!=OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
        assert(!pickups && !cancels && memcmp(&before,&runtime.throwState,sizeof(before))==0);free(blob);
    }
}
static void TargetGone(void) {
    for(unsigned pair=0;pair<4;pair++)for(unsigned held=0;held<2;held++) {
        Pair(pair,TRUE);if(held)assert(OverworldWildSpawns_StartCarriedThrowTarget(&state,carrier,cargoSlot));
        unsigned releases=releaseCalls;
        OverworldWildSpawns_ClearThrowStateForSlot(&state,cargoSlot);
        assert(runtime.throwState.targets[carrier]==0 && runtime.throwState.targets[other]==0);
        assert(runtime.throwState.targetMask==0 && runtime.throwState.carrierMask==0);
        assert(state.movementActorControlModes[cargoSlot]==0);
        for(unsigned i=0;i<2;i++) {
            unsigned slot=i?other:carrier;
            assert(!(conditions.bindings[slot].bindings[OVERWORLD_TARGET_BINDING_CARGO].flags&OVERWORLD_TARGET_BINDING_BOUND));
        }
        assert(releaseCalls==releases+(held?1u:0u));free(blob);
    }
}
static void UnrelatedFlight(void) {
    Pair(0,TRUE);
    /* A launched flight retains its target bit without a holder relation. */
    runtime.throwState.targetMask|=1u<<3;state.movementActorControlModes[3]=OW_WILD_ACTOR_CONTROL_HELD;
    OverworldWildSpawns_AbortThrow(&state,other);
    assert(runtime.throwState.targetMask==((1u<<cargoSlot)|(1u<<3)));
    OverworldWildSpawns_AbortThrow(&state,carrier);
    assert(runtime.throwState.targetMask==(1u<<3));
    assert(state.movementActorControlModes[3]==OW_WILD_ACTOR_CONTROL_HELD && !releaseCalls);free(blob);
}
static void IncomingAbort(void) {
    for(unsigned pair=0;pair<4;pair++)for(unsigned incomingHeld=0;incomingHeld<2;incomingHeld++)for(unsigned outgoingHeld=0;outgoingHeld<2;outgoingHeld++) {
        Pair(pair,TRUE);
        runtime.throwState.targets[other]=OW_WILD_HELPER_THROW_TARGET_ENCODE(carrier)|(incomingHeld?0x80:0);
        runtime.throwState.targets[carrier]|=outgoingHeld?0x80:0;
        runtime.throwState.targetMask|=1u<<carrier;
        state.movementActorControlModes[carrier]=incomingHeld?OW_WILD_ACTOR_CONTROL_HELD:0;
        state.movementActorControlModes[cargoSlot]=outgoingHeld?OW_WILD_ACTOR_CONTROL_HELD:0;
        conditions.bindings[other].bindings[OVERWORLD_TARGET_BINDING_CARGO].target.actor=Handle(carrier);
        claimStates[other].targetSlot=carrier;
        claimStates[other].targetGeneration=Handle(carrier).generation;
        claimStates[other].targetEncounterGeneration=Handle(carrier).encounterGeneration;
        OverworldTargetBindingsState before=conditions.bindings[other];
        OverworldBehaviorConditionEntryState entry=claimStates[other];
        OverworldActorRuntimeSlot actorBefore=actors.slots[carrier];
        unsigned releases=releaseCalls;
        OverworldWildSpawns_AbortThrow(&state,carrier);
        assert(runtime.throwState.targets[carrier]==0);
        assert(runtime.throwState.targets[other]==(OW_WILD_HELPER_THROW_TARGET_ENCODE(carrier)|(incomingHeld?0x80:0)));
        assert(runtime.throwState.carrierMask==(1u<<other));
        assert(runtime.throwState.targetMask==(1u<<carrier));
        assert(state.movementActorControlModes[carrier]==(incomingHeld?OW_WILD_ACTOR_CONTROL_HELD:0));
        assert(state.movementActorControlModes[cargoSlot]==0 && releaseCalls==releases+outgoingHeld);
        assert(!memcmp(&before,&conditions.bindings[other],sizeof(before)));
        assert(!memcmp(&entry,&claimStates[other],sizeof(entry)));
        assert(!memcmp(&actorBefore,&actors.slots[carrier],sizeof(actorBefore)));
        assert(!(claimStates[carrier].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE));
        OverworldWildSpawns_ClearThrowStateForSlot(&state,carrier);
        assert(!runtime.throwState.targets[other] && !runtime.throwState.targetMask && !runtime.throwState.carrierMask);
        assert(!conditions.bindings[other].bindings[OVERWORLD_TARGET_BINDING_CARGO].flags);
        assert(!(claimStates[other].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE));
        assert(state.movementActorControlModes[carrier]==0);
        assert(releaseCalls==releases+outgoingHeld+incomingHeld);free(blob);
    }
}
static void ReciprocalPickup(void) {
    for(unsigned pair=0;pair<4;pair++) {
        Pair(pair,FALSE);cargoSlot=other;
        conditions.bindings[carrier].bindings[OVERWORLD_TARGET_BINDING_CARGO].target.actor=Handle(other);
        conditions.bindings[other].bindings[OVERWORLD_TARGET_BINDING_CARGO].target.actor=Handle(carrier);
        claimStates[carrier].targetSlot=other;
        claimStates[other].targetSlot=carrier;
        assert(OverworldWildHelper_TryStartPickupThrowAction(&state,&runtime.throwState,
            &runtime.spawnPresentations,carrier,other,0,0));
        assert(OverworldWildHelper_TryStartPickupThrowAction(&state,&runtime.throwState,
            &runtime.spawnPresentations,other,carrier,0,0));
        OverworldActorHandle a=Handle(carrier),b=Handle(other);
        assert(Atomic(carrier,&a,&b)==OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL);
        OverworldTargetBindingsState before=conditions.bindings[carrier];
        OverworldBehaviorConditionEntryState entry=claimStates[carrier];
        assert(OverworldWildSpawns_StartCarriedThrowTarget(&state,carrier,other));
        assert(runtime.throwState.targets[carrier]==OW_WILD_HELPER_THROW_TARGET_ENCODE_CARRIED(other));
        assert(runtime.throwState.targets[other]==0);
        assert(runtime.throwState.targetMask==(1u<<other) && runtime.throwState.carrierMask==(1u<<carrier));
        assert(state.movementActorControlModes[other]==OW_WILD_ACTOR_CONTROL_HELD);
        assert(!memcmp(&before,&conditions.bindings[carrier],sizeof(before)));
        assert(!memcmp(&entry,&claimStates[carrier],sizeof(entry)));
        assert(!conditions.bindings[other].bindings[OVERWORLD_TARGET_BINDING_CARGO].flags);
        assert(!(claimStates[other].flags&OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE));
        unsigned committed=pickups;
        assert(!OverworldWildHelper_TryStartPickupThrowAction(&state,&runtime.throwState,
            &runtime.spawnPresentations,other,carrier,0,0));
        assert(Atomic(other,&b,&a)==OVERWORLD_PICKUP_ROUTE_EDGE_INVALID);
        assert(!OverworldWildSpawns_StartCarriedThrowTarget(&state,other,carrier));
        assert(!OverworldWildSpawns_StartCarriedThrowTarget(&state,carrier,other));
        assert(pickups==committed && runtime.throwState.targets[carrier]==OW_WILD_HELPER_THROW_TARGET_ENCODE_CARRIED(other));
        OverworldWildSpawns_ClearThrowStateForSlot(&state,other);
        assert(!runtime.throwState.targets[carrier] && !runtime.throwState.carrierMask && !runtime.throwState.targetMask);
        assert(state.movementActorControlModes[other]==0);free(blob);
    }
}
'''
