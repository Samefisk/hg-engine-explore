"""S0 checker controls, not gameplay proof or a replacement for facing S1."""

from pathlib import Path
import unittest

from scripts import verify_overworld_wild_walk_pause as pause
from scripts import verify_overworld_wild_flying_insect_walk as insect


ROOT = Path(__file__).resolve().parents[2]
SPAWNS = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
RUNTIME = ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c"
COMPLETION = "OverworldWildSpawns_HandleFinishedMovementCommand"
TICK = "OverworldWildSpawns_TickMovementParams"
LEDGE = "OverworldWildSpawns_TryStartLedgeJumpCommand"
REQUEST = "OverworldWildRuntime_RequestMotion"


def verify_ledge_pause_source(spawns, runtime):
    ledge = "".join(pause.function_body(spawns, LEDGE).split())
    request = "".join(pause.function_body(runtime, REQUEST).split())
    marker = "state->movementStagedHopPending[slot]=OW_WILD_SPAWNER_STAGED_HOP_LEDGE_PENDING;"
    start = "OverworldWildSpawns_StartPreparedCustomJumpCommand("
    if ledge.count(marker) != 1 or ledge.index(marker) >= ledge.index(start):
        raise AssertionError("ledge kind is not staged before shared motion")
    if "state->movementStagedHopPending[slot]=FALSE;" not in ledge:
        raise AssertionError("rejected ledge leaves a staged marker")
    if "state->movementStagedHopPending[slot]==OW_WILD_RUNTIME_STAGED_HOP_LEDGE_PENDING" not in request:
        raise AssertionError("ledge shared motion still owns hopPause")
    if "lane->hopPause" not in request:
        raise AssertionError("ordinary Hop lost its authored pause")


def verify_chain_forward_hop_pause_source(spawns, runtime):
    forward = "".join(
        pause.function_body(
            spawns, "OverworldWildSpawns_TryStartChainForwardHop"
        ).split()
    )
    planned = "".join(
        pause.function_body(
            spawns, "OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand"
        ).split()
    )
    request = "".join(pause.function_body(runtime, REQUEST).split())
    marker = "OW_WILD_SPAWNER_STAGED_CHAIN_HOP_FORWARD_PENDING"
    runtime_marker = "OW_WILD_RUNTIME_STAGED_CHAIN_HOP_FORWARD_PENDING"
    forward_call = (
        "OverworldWildSpawns_TryStartBehaviorHopToPlannedTileCommand("
        "state,state->movementFieldSystem,slot,profile,"
        "allowedTile|OW_WILD_SPAWNER_WALK_STRICT_DIAGONAL_MARKER,"
        "targetX,targetY,targetX,targetY," + marker + ")"
    )
    staged = (
        "state->movementStagedHopPending[slot]=pendingMarker!=0"
        "?pendingMarker:flatWalk?OW_WILD_SPAWNER_STAGED_WALK_PENDING:TRUE;"
    )
    start = "OverworldWildSpawns_StartPreparedCustomJumpCommandTimed("
    if forward_call not in forward:
        raise AssertionError("forward Hop does not pass its staged marker")
    if (planned.count(staged) != 1
            or planned.index(staged) >= planned.index(start)):
        raise AssertionError("forward Hop is not staged before shared motion")
    expected_pause = (
        "intent.pauseFrames=kind==OVERWORLD_MOTION_KIND_REPOSITION"
        "||(kind==OVERWORLD_MOTION_KIND_HOP"
        "&&(state->movementStagedHopPending[slot]"
        "==OW_WILD_RUNTIME_STAGED_HOP_LEDGE_PENDING"
        "||state->movementStagedHopPending[slot]==" + runtime_marker + "))"
        "?0:kind==OVERWORLD_MOTION_KIND_WALK"
        "?OverworldWildSpawns_ResolveWalkPause(lane):lane->hopPause;"
    )
    if expected_pause not in request:
        raise AssertionError("forward Hop shared motion still owns hopPause")


def verify_walk_sway_source(spawns):
    start = insect.function_bodies(spawns)[
        "OverworldWildSpawns_StartPreparedCustomJumpCommandTimed"
    ]
    normalized = "".join(insect.strip_c_noncode(start).split())
    expected = "".join("""
        swayWidth = chainReposition
            ? 0
            : flatWalk
                ? OW_WILD_BEHAVIOR_WALK_SWAY_WIDTH(lane->walkOptions)
                : lane->hopSwayWidth;
    """.split())
    if expected not in normalized:
        raise AssertionError("flat Walk does not use its authored sway width")


class WildWalkSourceChecksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.spawns = SPAWNS.read_text()
        cls.runtime = RUNTIME.read_text()

    def test_ledge_hop_uses_only_the_walk_completion_pause(self):
        verify_ledge_pause_source(self.spawns, self.runtime)

    def test_chain_forward_hop_has_no_shared_motion_settle_pause(self):
        verify_chain_forward_hop_pause_source(self.spawns, self.runtime)

    def test_chain_forward_hop_pause_control_rejects_missing_exemption(self):
        marker = "OW_WILD_RUNTIME_STAGED_CHAIN_HOP_FORWARD_PENDING"
        self.assertEqual(self.runtime.count(marker), 2)
        with self.assertRaisesRegex(AssertionError, "still owns hopPause"):
            verify_chain_forward_hop_pause_source(
                self.spawns,
                self.runtime.replace(
                    "            == " + marker,
                    "            == OW_WILD_RUNTIME_STAGED_HOP_LEDGE_PENDING",
                    1,
                ),
            )

    def test_chain_forward_hop_pause_controls_preserve_other_motion(self):
        with self.assertRaisesRegex(AssertionError, "still owns hopPause"):
            verify_chain_forward_hop_pause_source(
                self.spawns,
                self.runtime.replace(
                    "        || (kind == OVERWORLD_MOTION_KIND_HOP",
                    "        || (kind == OVERWORLD_MOTION_KIND_WALK",
                    1,
                ),
            )
        with self.assertRaisesRegex(AssertionError, "still owns hopPause"):
            verify_chain_forward_hop_pause_source(
                self.spawns,
                self.runtime.replace(": lane->hopPause;", ": 0 * lane->hopPause;", 1),
            )

    def test_chain_forward_hop_marker_must_precede_motion_start(self):
        staged = """    state->movementStagedHopPending[slot] = pendingMarker != 0
        ? pendingMarker
        : flatWalk ? OW_WILD_SPAWNER_STAGED_WALK_PENDING : TRUE;
"""
        self.assertEqual(self.spawns.count(staged), 1)
        start = """    } else if (OverworldWildSpawns_StartPreparedCustomJumpCommandTimed(
            state,
            fieldSystem,
            slot,
            object,
            direction,
            distance,
            landingX,
            landingY,
            profile,
            pendingMarker != 0,
            0) == OVERWORLD_MOTION_DECISION_ACCEPTED) {
        return TRUE;
"""
        self.assertEqual(self.spawns.count(start), 1)
        moved = self.spawns.replace(staged, "", 1).replace(
            start,
            start.replace("        return TRUE;\n", staged + "        return TRUE;\n"),
            1,
        )
        with self.assertRaisesRegex(AssertionError, "not staged"):
            verify_chain_forward_hop_pause_source(moved, self.runtime)

    def test_ledge_pause_source_controls_reject_old_double_pause(self):
        marker = """    state->movementStagedHopPending[slot] =
        OW_WILD_SPAWNER_STAGED_HOP_LEDGE_PENDING;
"""
        self.assertEqual(self.spawns.count(marker), 1)
        with self.assertRaisesRegex(AssertionError, "not staged"):
            verify_ledge_pause_source(self.spawns.replace(marker, "", 1), self.runtime)
        guard = """kind == OVERWORLD_MOTION_KIND_REPOSITION
        || (kind == OVERWORLD_MOTION_KIND_HOP
            && (state->movementStagedHopPending[slot]
                    == OW_WILD_RUNTIME_STAGED_HOP_LEDGE_PENDING
                || state->movementStagedHopPending[slot]
                    == OW_WILD_RUNTIME_STAGED_CHAIN_HOP_FORWARD_PENDING))"""
        self.assertEqual(self.runtime.count(guard), 1)
        with self.assertRaisesRegex(AssertionError, "still owns hopPause"):
            verify_ledge_pause_source(
                self.spawns,
                self.runtime.replace(
                    guard,
                    """kind == OVERWORLD_MOTION_KIND_REPOSITION
        || (kind == OVERWORLD_MOTION_KIND_HOP
            && state->movementStagedHopPending[slot]
                == OW_WILD_RUNTIME_STAGED_CHAIN_HOP_FORWARD_PENDING)""",
                    1,
                ),
            )

    def test_definition_not_forward_declaration_or_call(self):
        source = '''
static void finish(int slot);
static void other(void) { if (finish(3)) { unrelated(); } }
static void finish(int slot) {
    /* An unmatched brace here: } */
    const char *text = "{";
    authored_pause();
}
'''
        body = pause.function_body(source, "finish")
        self.assertIn("authored_pause();", body)
        self.assertNotIn("unrelated();", body)
        with self.assertRaises(SystemExit):
            pause.function_body("static void finish(int slot);\nvoid other(void) {}", "finish")

    def test_current_three_lane_routing(self):
        pause.verify_walk_pause_routing(self.spawns)
        self.assertEqual(pause.function_body(self.spawns, COMPLETION).count("lane->walkPause"), 3)

    def test_each_missing_lane_and_follower_special_case_fail(self):
        body = pause.function_body(self.spawns, COMPLETION)
        pieces = body.split("lane->walkPause")
        self.assertEqual(len(pieces), 4)
        for lane in range(3):
            changed = pieces[0]
            for index, piece in enumerate(pieces[1:]):
                changed += ("0" if index == lane else "lane->walkPause") + piece
            with self.subTest(lane=lane), self.assertRaises(SystemExit):
                pause.verify_walk_pause_routing(self.spawns.replace(body, changed, 1))
        changed = "if (slot == OW_WILD_FOLLOWER_SLOT) return;\n" + body
        with self.assertRaises(SystemExit):
            pause.verify_walk_pause_routing(self.spawns.replace(body, changed, 1))

    def test_current_facing_guard_and_whitespace(self):
        insect.verify_face_player_call_gating(self.spawns)
        body = insect.function_bodies(self.spawns)[TICK]
        changed = body.replace(
            "&& (!actorPolicyKnown",
            "&& /* active chain owner */\n (!actorPolicyKnown",
            1,
        )
        self.assertNotEqual(body, changed)
        insect.verify_face_player_call_gating(self.spawns.replace(body, changed, 1))

    def test_weakened_option_grid_guard_or_ungated_call_fail(self):
        body = insect.function_bodies(self.spawns)[TICK]
        for before, after in (
            ("if (OW_WILD_BEHAVIOR_WALK_FACES_PLAYER(profile.owner.walkOptions)", "if (1"),
            ("&& (!actorPolicyKnown", "|| (!actorPolicyKnown"),
            ("!= OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER)", "== OW_WILD_SPAWNER_CHAIN_REPOSITION_GRID_MARKER)"),
        ):
            self.assertIn(before, body)
            changed = body.replace(before, after, 1)
            with self.subTest(mutation=after), self.assertRaises(SystemExit):
                insect.verify_face_player_call_gating(self.spawns.replace(body, changed, 1))
        changed = body + "\nOverworldWildSpawns_ApplyFacePlayerFacing(state, i, 1);\n"
        with self.assertRaises(SystemExit):
            insect.verify_face_player_call_gating(self.spawns.replace(body, changed, 1))

    def test_motion_owner_blocks_idle_walk_but_not_face_player(self):
        insect.verify_walk_start_requires_idle_motion(self.spawns)
        body = insect.function_bodies(self.spawns)[TICK]
        face_guard = "if (OW_WILD_BEHAVIOR_WALK_FACES_PLAYER(profile.owner.walkOptions)"
        self.assertIn(face_guard, body)
        changed = body.replace(
            face_guard,
            "if (!actorMotionOwnsFacing && OW_WILD_BEHAVIOR_WALK_FACES_PLAYER(profile.owner.walkOptions)",
            1,
        )
        with self.assertRaises(SystemExit):
            insect.verify_face_player_call_gating(
                self.spawns.replace(body, changed, 1)
            )
        for before, after in (
            ("&& policy.motionPhase < OVERWORLD_MOTION_PHASE_CANCELED;", ";"),
            ("if (actorMotionOwnsFacing) {", "if (FALSE) {"),
        ):
            self.assertIn(before, body)
            changed = body.replace(before, after, 1)
            with self.subTest(mutation=after), self.assertRaises(SystemExit):
                insect.verify_face_player_call_gating(
                    self.spawns.replace(body, changed, 1)
                )
        start = insect.function_bodies(self.spawns)[
            "OverworldWildSpawns_TryStartSpawnerMovementCommand"
        ]
        changed = start.replace(
            "if (policy.motionPhase > OVERWORLD_MOTION_PHASE_IDLE",
            "if (FALSE && policy.motionPhase > OVERWORLD_MOTION_PHASE_IDLE",
            1,
        )
        with self.assertRaises(SystemExit):
            insect.verify_walk_start_requires_idle_motion(
                self.spawns.replace(start, changed, 1)
            )

    def test_diagonal_walk_start_preserves_authored_facing(self):
        start = insect.function_bodies(self.spawns)[
            "OverworldWildSpawns_StartPreparedCustomJumpCommandTimed"
        ]
        normalized = "".join(insect.strip_c_noncode(start).split())
        expected = "".join("""
            preserveFacing
                || (spinSpeed & OW_WILD_SPAWNER_CUSTOM_JUMP_SPIN_SPEED_MASK) != 0
                || (flatWalk && (object->flags & MAPOBJECTFLAG_UNK7) != 0)
            ? spinStartFacing
            : flatWalk
                && direction > OW_WILD_MOVEMENT_DIAGNOSTIC_DIRECTION_RIGHT
            ? OverworldWalk_DiagonalFacing(
                object,
                direction,
                OverworldWalk_DirectionKey(direction))
            : direction
        """.split())
        self.assertIn(
            expected,
            normalized,
            "a diagonal Walk can overwrite face-player or fixed facing on "
            "its first frame",
        )

    def test_flat_walk_uses_its_own_sway_width(self):
        verify_walk_sway_source(self.spawns)
        changed = self.spawns.replace(
            "OW_WILD_BEHAVIOR_WALK_SWAY_WIDTH(lane->walkOptions)",
            "lane->hopSwayWidth",
            1,
        )
        self.assertNotEqual(self.spawns, changed)
        with self.assertRaisesRegex(AssertionError, "authored sway width"):
            verify_walk_sway_source(changed)


if __name__ == "__main__":
    unittest.main()
