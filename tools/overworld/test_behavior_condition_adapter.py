from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HEADER = ROOT / "include/overworld_behavior_condition_adapter.h"
SOURCE = ROOT / "lib/overworld/overworld_behavior_condition_adapter.c"
WILD_SOURCE = (
    ROOT
    / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
)
SERVICE_SOURCE = (
    ROOT
    / "src/overworld_follower_selector_overlay/overworld_behavior_condition_service.c"
)
WALK_SOURCE = ROOT / "src/pokemon_move_history_overlay/overworld_walk_module.c"
def function(source: str, name: str, next_name: str) -> str:
    start = source.index(name)
    end = source.index(next_name, start)
    return source[start:end]


class BehaviorConditionAdapterTests(unittest.TestCase):
    def test_adapter_v10_outcome_exposes_independent_timed_endings(self):
        harness = r"""
#include "overworld_behavior_condition_adapter.h"

typedef char VersionMustBe10[
    OVERWORLD_BEHAVIOR_CONDITION_ADAPTER_VERSION == 10 ? 1 : -1];
typedef char EntryMustBe28[
    sizeof(OverworldBehaviorConditionAdapterEntry) == 28 ? 1 : -1];
typedef char OutcomeMustBe6[
    sizeof(OverworldBehaviorConditionAdapterOutcome) == 6 ? 1 : -1];
typedef char TargetDxOffsetMustBe2[
    offsetof(OverworldBehaviorConditionAdapterOutcome,
        targetDx) == 2 ? 1 : -1];
typedef char TimedWinnerMaskMustBeU32[
    sizeof(((OverworldWildBehaviorConditionRuntime *)0)
        ->timedWinningApplicationMasks[0]) == sizeof(u32) ? 1 : -1];
"""
        with tempfile.TemporaryDirectory(
            prefix="behavior-condition-adapter-"
        ) as directory:
            source = Path(directory) / "adapter_layout.c"
            source.write_text(harness)
            command = [
                "arm-none-eabi-gcc",
                "-std=c11",
                "-mthumb",
                "-mcpu=arm946e-s",
                "-Wall",
                "-Wextra",
                "-fsyntax-only",
                "-I",
                str(ROOT / "include"),
                str(source),
            ]
            compiled = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(
                compiled.returncode,
                0,
                compiled.stdout + compiled.stderr,
            )

    def test_timed_winner_endings_are_tracked_per_application(self):
        source = SOURCE.read_text()
        evaluation = function(
            source,
            "OverworldBehaviorConditionAdapter_EvaluateActor(",
            "const OverworldBehaviorConditionAdapterEntry",
        )
        self.assertNotIn("timedConditionActive", source)
        self.assertIn("1u << entry->applicationIndex", evaluation)
        self.assertIn(
            "runtime->timedWinningApplicationMasks[slot]", evaluation
        )
        self.assertIn("& ~timedWinningApplicationMask", evaluation)
        self.assertIn("endedTimedApplicationMask", evaluation)
        self.assertNotIn("outcome->endedTimedApplicationMask", evaluation)

    def test_retrigger_only_requests_presentation_when_resolution_changes(self):
        source = SOURCE.read_text()
        evaluation = function(
            source,
            "OverworldBehaviorConditionAdapter_EvaluateActor(",
            "const OverworldBehaviorConditionAdapterEntry",
        )
        self.assertIn("runtime->result.triggeredApplicationMask", evaluation)
        self.assertIn(
            "OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED",
            evaluation,
        )

    def test_trace_is_subject_bound_and_contains_available_state(self):
        source = SOURCE.read_text()
        evaluation = function(
            source,
            "OverworldBehaviorConditionAdapter_EvaluateActor(",
            "const OverworldBehaviorConditionAdapterEntry",
        )
        trace = function(
            WALK_SOURCE.read_text(),
            "OverworldBehaviorConditionTrace_Record(",
            "OverworldWalk_ProposeStep(",
        )
        self.assertIn("&prepared->subject", evaluation)
        self.assertNotIn("traceActor", evaluation)
        self.assertNotIn("&result->resolvedTarget.actor,", trace)
        for required in (
            "OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRIGGERED",
            "OVERWORLD_BEHAVIOR_CONDITION_SCRATCH_TRUE",
            "entry->activationMode",
            "OVERWORLD_BEHAVIOR_CONDITION_TRACE_RECORD(",
        ):
            self.assertIn(required, evaluation)
        for required in (
            "entryState->activeUntil",
            "entryState->cooldownUntil",
            "resolvedTarget.actor.slot",
        ):
            self.assertIn(required, trace)

    def test_follower_slot_uses_authoritative_mounted_role(self):
        source = SOURCE.read_text()
        frame = function(
            source,
            "OverworldBehaviorConditionAdapter_BuildFrame(",
            "OverworldBehaviorConditionAdapter_ResolveTarget(",
        )
        self.assertIn("OVERWORLD_ACTOR_INSPECT_ACTOR_INDEX", frame)
        self.assertIn("query.index = (u8)slot", frame)
        self.assertIn(
            "actorRole == OVERWORLD_ACTOR_ROLE_MOUNTED",
            frame,
        )
        service = SERVICE_SOURCE.read_text()
        self.assertIn("OverworldBehaviorConditionService_Get(void)", service)
        self.assertIn("OverworldFollowerSelector_IsDirectLoaded()", service)
        self.assertIn("OverworldBehaviorConditionAdapter_HandleEquals", frame)

    def test_cross_overlay_service_gate_preserves_thumb_state(self):
        source = SOURCE.read_text()
        linker = (
            ROOT / "src/overworld_actor_system_overlay/linker.ld"
        ).read_text()
        header = (
            ROOT / "include/overworld_behavior_condition_runtime.h"
        ).read_text()
        self.assertIn("OVERWORLD_BEHAVIOR_CONDITION_SERVICE_GATE()", source)
        self.assertIn("OverworldBehaviorConditionServiceGetFunc", header)
        self.assertNotIn(
            "OverworldBehaviorConditionService_Get =",
            linker,
        )
        self.assertIn(
            "OVERWORLD_BEHAVIOR_CONDITION_TRACE_RECORD_ADDR | 1u",
            (ROOT / "include/overworld_behavior_condition_adapter.h").read_text(),
        )
        self.assertNotIn(
            "OverworldBehaviorConditionTrace_Record =",
            linker,
        )

    def test_service_owns_exact_per_actor_state_allocation(self):
        adapter = SOURCE.read_text()
        runtime = (
            ROOT / "lib/overworld/overworld_behavior_condition_runtime.c"
        ).read_text()
        prepare = function(
            adapter,
            "OverworldBehaviorConditionAdapter_PrepareActor(",
            "OverworldBehaviorConditionAdapter_HandleEquals(",
        )
        self.assertNotIn("OverworldBehaviorConditionAdapter_Allocate", adapter)
        self.assertEqual(prepare.count("service->prepareActor("), 1)
        self.assertIn("sys_AllocMemory(\n            HEAPID_WORLD,", runtime)
        self.assertIn("prepared->count * sizeof(*prepared->states)", runtime)
        self.assertIn("OverworldBehaviorConditionAdapter_Free", adapter)

    def test_unchanged_application_mask_reuses_the_actor_profile(self):
        adapter = function(
            SOURCE.read_text(),
            "OverworldBehaviorConditionAdapter_EvaluateActor(",
            "const OverworldBehaviorConditionAdapterEntry",
        )
        wild = function(
            WILD_SOURCE.read_text(),
            "OverworldWildSpawns_EvaluateConditionsForSlot(",
            "static BOOL OverworldWildSpawns_BehaviorSlotCacheMatches(",
        )
        self.assertIn(
            "runtime->result.activeApplicationMask\n"
            "            != runtime->activeApplicationMasks[slot]",
            adapter,
        )
        self.assertIn(
            "OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED",
            adapter,
        )
        self.assertIn(
            "OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_PROFILE_CHANGED",
            wild,
        )
        self.assertIn(
            "outcome.flags\n"
            "            & (OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TRIGGERED\n"
            "                | OVERWORLD_BEHAVIOR_CONDITION_OUTCOME_TIMED_ENDED)",
            wild,
        )

    def test_wild_runtime_owns_nested_condition_state_cleanup(self):
        source = WILD_SOURCE.read_text()
        clear_record = function(
            source,
            "OverworldWildSpawns_ClearConditionActorRecord(",
            "static void OverworldWildSpawns_ClearConditionSlot(",
        )
        cleanup = function(
            source,
            "OverworldWildSpawns_ClearConditionActorRecord(",
            "static BOOL OverworldWildSpawns_PrepareConditionsForSlot(",
        )
        self.assertIn("sys_FreeMemoryEz(prepared->states)", clear_record)
        self.assertIn("prepared->states = NULL", clear_record)
        self.assertIn("prepared->valid = FALSE", clear_record)
        self.assertIn(
            "conditions->activeApplicationMasks[slot] = 0", clear_record
        )
        self.assertIn(
            "OVERWORLD_BEHAVIOR_CONDITION_MAX_ACTORS", cleanup
        )
        self.assertNotIn("GetConditionAdapter", cleanup)


if __name__ == "__main__":
    unittest.main()
