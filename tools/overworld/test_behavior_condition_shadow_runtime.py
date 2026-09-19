#!/usr/bin/env python3

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WILD = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
SHADOW = ROOT / "lib/overworld/overworld_behavior_condition_shadow.c"
RUNTIME = ROOT / "lib/overworld/overworld_behavior_condition_runtime.c"
RUNTIME_HEADER = ROOT / "include/overworld_behavior_condition_runtime.h"
SHADOW_HEADER = ROOT / "include/overworld_behavior_condition_shadow.h"
ACTOR_LINKER = ROOT / "src/overworld_actor_system_overlay/linker.ld"


def function(source: str, name: str, next_name: str) -> str:
    start = source.index(name)
    end = source.index(next_name, start)
    return source[start:end]


class BehaviorConditionShadowRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wild = WILD.read_text()
        cls.shadow = SHADOW.read_text()
        cls.runtime = RUNTIME.read_text()
        cls.runtime_header = RUNTIME_HEADER.read_text()
        cls.shadow_header = SHADOW_HEADER.read_text()
        cls.actor_linker = ACTOR_LINKER.read_text()

    def test_bind_prepares_before_visible_spawn_startup(self):
        startup = function(
            self.wild,
            "OverworldWildSpawns_StartSpawnStartup(",
            "OverworldWildSpawns_CountActiveBehaviorLimitKey(",
        )
        self.assertLess(startup.index("->bindActor("),
                        startup.index("PrepareConditionShadowForSlot("))
        self.assertLess(startup.index("PrepareConditionShadowForSlot("),
                        startup.index("SeedPreparedBehaviorProfile("))
        prepare = function(
            self.shadow,
            "OverworldBehaviorConditionShadow_Prepare(",
            "OverworldBehaviorConditionShadow_BuildFrame(",
        )
        self.assertIn("service->prepareActor(", prepare)
        self.assertIn("runtime->frame.valid = FALSE", prepare)

    def test_lifecycle_clears_owned_state(self):
        self.assertIn("ClearConditionShadowSlot(state, slot);", self.wild)
        self.assertIn("ClearAllConditionShadowState(state);", self.wild)
        clear = function(
            self.shadow,
            "OverworldBehaviorConditionShadow_ClearSlot(",
            "OverworldBehaviorConditionShadow_ClearAll(",
        )
        self.assertIn("memset(&runtime->actors[slot]", clear)
        self.assertIn("runtime->frame.valid = FALSE", clear)
        self.assertIn("memset(runtime, 0, sizeof(*runtime))", self.shadow)

    def test_shadow_runs_only_after_motion_owner_returns_idle(self):
        tick = function(
            self.wild,
            "OverworldWildSpawns_TickMovementParams(",
            "OverworldWildSpawns_UpdateSpawnerMovementCommand(",
        )
        motion_guard = tick.index("if (actorMotionOwnsFacing)")
        shadow_call = tick.index("OverworldWildSpawns_RunConditionShadowForSlot(")
        legacy_active = tick.index(
            "movementSpotStates[i] == OW_WILD_SPAWNER_SPOT_STATE_ACTIVE",
            shadow_call,
        )
        self.assertLess(motion_guard, shadow_call)
        self.assertLess(shadow_call, legacy_active)
        self.assertNotIn("shadow->resolution.profile", tick)

    def test_one_bounded_frame_roster_is_reused(self):
        build = function(
            self.shadow,
            "OverworldBehaviorConditionShadow_BuildFrame(",
            "OverworldBehaviorConditionShadow_Resolve(",
        )
        self.assertIn("runtime->frame.valid", build)
        self.assertIn("runtime->frame.world.frame == systemSnapshot.frame", build)
        self.assertIn("slot < OW_WILD_MAX_SPAWNS", build)
        self.assertNotIn("conditionEntries", build)
        self.assertIn("maxPreparedCount", self.shadow)
        self.assertIn("OVERWORLD_BEHAVIOR_CONDITION_MAX_ENTRIES", self.runtime_header)
        self.assertIn("PreparedActorBudgetMustRemain848Bytes", self.runtime_header)
        self.assertIn("ScratchBudgetMustRemain1408Bytes", self.runtime_header)

    def test_targets_use_full_generation_safe_handles(self):
        for field in (
            "slot", "generation", "fieldEpoch", "mapGeneration",
            "encounterGeneration",
        ):
            self.assertIn(f"left->{field} == right->{field}", self.shadow)
            self.assertIn(f"left->{field} == right->{field}", self.runtime)
        run = function(
            self.shadow,
            "OverworldBehaviorConditionShadow_Run(",
            "gOverworldBehaviorConditionShadowEntry",
        )
        self.assertIn("OverworldBehaviorConditionShadow_HandleEquals(", run)
        self.assertIn("memset(prepared, 0, sizeof(*prepared))", run)

    def test_resolver_receives_only_explicit_condition_results(self):
        resolve = function(
            self.shadow,
            "OverworldBehaviorConditionShadow_Resolve(",
            "OverworldBehaviorConditionShadow_RecordTrace(",
        )
        self.assertIn("BEHAVIOR_RESOLVE_CONDITIONS_EXPLICIT", resolve)
        self.assertIn("runtime->result.activeApplicationMask", resolve)
        self.assertIn("runtime->result.resolvedTargetSourceApplication", resolve)
        self.assertIn("runtime->result.resolvedTargetConditionId", resolve)

    def test_trace_work_is_armed_only_and_contains_required_facts(self):
        trace = function(
            self.shadow,
            "OverworldBehaviorConditionShadow_RecordTrace(",
            "OverworldBehaviorConditionShadow_Run(",
        )
        self.assertIn("if (!runtime->frame.traceArmed)", trace)
        guard = trace.index("if (!runtime->frame.traceArmed)")
        first_event = trace.index("OVERWORLD_ACTOR_EVENT_CONDITION_EVALUATED")
        self.assertLess(guard, first_event)
        for event in (
            "OVERWORLD_ACTOR_EVENT_CONDITION_EVALUATED",
            "OVERWORLD_ACTOR_EVENT_CONDITION_TIMERS",
            "OVERWORLD_ACTOR_EVENT_CONDITION_TARGET",
            "OVERWORLD_ACTOR_EVENT_CONDITIONAL_RESOLVED",
        ):
            self.assertIn(event, trace)

    def test_temporary_bridge_preserves_actor_abi(self):
        self.assertIn("OVERWORLD_BEHAVIOR_CONDITION_SHADOW_ENTRY_ADDR 0x023B6500",
                      self.shadow_header)
        self.assertIn("ORIGIN = 0x023B6500, LENGTH = 0x4600", self.actor_linker)
        self.assertIn("ACTOR_CORE_ORIGIN = 0x023B6B00", self.actor_linker)
        self.assertIn("condition shadow bridge exceeds temporary reserve",
                      self.actor_linker)


if __name__ == "__main__":
    unittest.main()
