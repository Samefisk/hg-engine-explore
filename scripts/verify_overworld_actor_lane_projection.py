#!/usr/bin/env python3
"""D2 host regression: native controller state is not a resolved profile lane.

Runs the unchanged production FillActorView and SyncLegacyActor bodies through
the existing view fixture. Only engine boundaries are stubbed. This D2 check
is separate from host.actor-view; it is not ROM or gameplay proof.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "actor_view_fixture", ROOT / "scripts/verify_overworld_actor_view.py")
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load existing actor-view fixture")
view_fixture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(view_fixture)


DRIVER = r'''
/* Expectations come from the public lane contract: the Owner lane handles
 * Chill and Emoting; Tired selects its resolved lane.
 * Mounted control always selects Owner. Native controller state stays raw.
 * ExpectedView supplies the prior fixture's exact preservation expectations;
 * only these two independently specified projection fields are replaced.
 */
int main(void)
{
    const unsigned nativeStates[] = {
        OW_WILD_SPAWNER_SPOT_STATE_CHILL,
        OW_WILD_SPAWNER_SPOT_STATE_EMOTING,
        OW_WILD_SPAWNER_SPOT_STATE_RESERVED,
        OW_WILD_SPAWNER_SPOT_STATE_TIRED,
        4, 255,
    };
    const unsigned semanticLanes[] = {
        BEHAVIOR_RESOLUTION_LANE_OWNER,
        BEHAVIOR_RESOLUTION_LANE_OWNER,
        BEHAVIOR_RESOLUTION_LANE_NONE,
        BEHAVIOR_RESOLUTION_LANE_TIRED,
        BEHAVIOR_RESOLUTION_LANE_NONE, BEHAVIOR_RESOLUTION_LANE_NONE,
    };
    const unsigned roles[] = {
        OVERWORLD_ACTOR_ROLE_WILD,
        OVERWORLD_ACTOR_ROLE_FOLLOWER,
        OVERWORLD_ACTOR_ROLE_MOUNTED,
    };
    for (unsigned roleIndex = 0; roleIndex < 3; roleIndex++)
    for (unsigned stateIndex = 0; stateIndex < sizeof(nativeStates) / sizeof(nativeStates[0]); stateIndex++)
    for (unsigned phase = OVERWORLD_MOTION_PHASE_IDLE;
         phase <= OVERWORLD_MOTION_PHASE_CANCELED; phase++)
    for (unsigned seed = 0; seed < 2; seed++) {
        const unsigned role = roles[roleIndex];
        const unsigned slot = role == OVERWORLD_ACTOR_ROLE_WILD
            ? 0 : OW_WILD_FOLLOWER_SLOT;
        const unsigned nativeState = nativeStates[stateIndex];
        mounted = role == OVERWORLD_ACTOR_ROLE_MOUNTED;
        const unsigned expectedLane = mounted
            ? BEHAVIOR_RESOLUTION_LANE_OWNER : semanticLanes[stateIndex];
        const unsigned expectedController = mounted
            ? OW_WILD_SPAWNER_SPOT_STATE_CHILL : nativeState;
        OverworldWildSpawnState state;
        FieldSystem field;
        MapObjectMan manager;
        PlayerAvatar avatar;
        LocalMapObject pokemon, player;
        Arrange(&state, &field, &manager, &avatar, &pokemon, &player, slot, 0, 0);
        state.movementSpotStates[slot] = (u8)nativeState;
        const OverworldWildSpawnState savedState = state;
        const LocalMapObject savedPokemon = pokemon, savedPlayer = player;
        struct { u64 prefix; OverworldActorStateSnapshot view; u64 suffix; } guarded;
        guarded.prefix = 0x123456789ABCDEFull;
        guarded.suffix = 0xFEDCBA9876543210ull;
        guarded.view = Seed(seed, phase);
        OverworldActorStateSnapshot expected = ExpectedView(guarded.view, slot, phase, 0, 0);
        expected.lane = (u8)expectedLane;
        expected.controllerState = (u8)expectedController;
        OverworldWildRuntime_FillActorView(&field, &state, slot, &guarded.view);
        if (guarded.view.lane != expectedLane
            || guarded.view.controllerState != expectedController) {
            fprintf(stderr,
                "lane projection role=%u native=%u: lane=%u expected=%u; controller=%u expected=%u\n",
                role, nativeState, guarded.view.lane, expectedLane,
                guarded.view.controllerState, expectedController);
        }
        CHECK(guarded.view.lane == expectedLane);
        CHECK(guarded.view.controllerState == expectedController);
        CheckSnapshot(&guarded.view, &expected);
        CHECK(guarded.prefix == 0x123456789ABCDEFull
            && guarded.suffix == 0xFEDCBA9876543210ull);
        CHECK(memcmp(&state, &savedState, sizeof(state)) == 0);
        CHECK(memcmp(&pokemon, &savedPokemon, sizeof(pokemon)) == 0);
        CHECK(memcmp(&player, &savedPlayer, sizeof(player)) == 0);
        fillCases++;

        memset(&gOverworldActorSystemState, 0x57, sizeof(gOverworldActorSystemState));
        OverworldActorStateSnapshot before = Seed(seed, phase);
        before.handle.slot = (u16)slot;
        before.handle.mapGeneration = 73;
        before.handle.encounterGeneration = 29;
        before.subjectIdentity = 0x76543210;
        before.role = (u8)role;
        before.inputOwnership = (u8)mounted;
        before.presentationAttached = TRUE;
        before.lane = (u8)(expectedLane == BEHAVIOR_RESOLUTION_LANE_OWNER
            ? BEHAVIOR_RESOLUTION_LANE_TIRED
            : BEHAVIOR_RESOLUTION_LANE_OWNER);
        gOverworldActorSystemState.slots[slot].snapshot = before;
        expected = ExpectedView(before, slot, phase, 0, 0);
        expected.lane = (u8)expectedLane;
        expected.controllerState = (u8)expectedController;
        bindCalls = unbindCalls = traceCount = 0;
        ActorSystem_SyncLegacyActor(&field, &state, slot);
        CheckSnapshot(&gOverworldActorSystemState.slots[slot].snapshot, &expected);
        CHECK(bindCalls == 0 && unbindCalls == 0);
        CHECK(traceCount == 1);
        CHECK(traces[0].event == OVERWORLD_ACTOR_EVENT_LANE_CHANGED);
        CHECK(traces[0].a == before.lane && traces[0].b == expectedLane);
        CHECK(memcmp(&traces[0].handle, &before.handle, sizeof(before.handle)) == 0);
        for (unsigned index = 0; index < 8; index++) {
            CHECK(gOverworldActorSystemState.slots[slot].policyGuard[index] == 0x57575757);
            CHECK(gOverworldActorSystemState.slots[slot].motionGuard[index] == 0x57575757);
        }
        CHECK(memcmp(&state, &savedState, sizeof(state)) == 0);
        CHECK(memcmp(&pokemon, &savedPokemon, sizeof(pokemon)) == 0);
        CHECK(memcmp(&player, &savedPlayer, sizeof(player)) == 0);
        syncCases++;
    }
    printf("PASS actual actor lane projection: %u Fill cases, %u Sync cases; %u assertions\n",
        fillCases, syncCases, assertions);
    return 0;
}
'''


def harness_source() -> str:
    source = view_fixture.harness_source()
    main = "\nint main(void)"
    include = '#include "overworld_motion_model.h"'
    if source.count(main) != 1 or source.count(include) != 1:
        raise ValueError("existing actor-view fixture driver boundary changed")
    # Keep the existing matrix and shared public constants intact. This
    # matrix independently covers every native lane and unknown state.
    source = source.replace(main, "\nint legacy_view_matrix_main(void)")
    return source + DRIVER


def main() -> int:
    source = harness_source()
    baseline = view_fixture.execute(source)
    if baseline.returncode:
        print("FAIL D2 actor lane projection (host only)")
        print(baseline.stdout + baseline.stderr, end="")
        return 1
    print(baseline.stdout, end="")
    marker = "view->presentationState = 0;"
    if source.count(marker) != 1:
        raise ValueError("production lane mutation seam changed")
    mutations = {
        "raw controller used as lane":
            "view->lane = state->movementSpotStates[slot];",
        "semantic lane used as controller":
            "view->controllerState = view->lane;",
    }
    for label, statement in mutations.items():
        mutant = view_fixture.execute(source.replace(marker, marker + " " + statement))
        if mutant.returncode != 1 or "actor view invariant failed" not in mutant.stderr:
            raise RuntimeError(f"known-bad actor lane projection did not fail: {label}")
        print(f"PASS known-bad actor lane projection rejected: {label}")
    print("PASS S1 actor lane projection; engine stubs, no gameplay claim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
