"""Execute real facade command bodies; host stubs are not native/game proof."""
from pathlib import Path
import re
import unittest

from scripts.verify_overworld_spawn_profile_lifecycle import production_function
from scripts.verify_overworld_actor_commit_sequence import execute

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c"


def harness_source():
    source = SOURCE.read_text()
    # Only host linkage changes; all executable statements remain verbatim.
    source = source.replace("\nOverworldActorResult __attribute__", "\nstatic OverworldActorResult __attribute__")
    source = source.replace("\nOverworldActorFrameResult __attribute__", "\nstatic OverworldActorFrameResult __attribute__")
    bodies = []
    for name, result in (("ActorSystem_ReleaseTarget", "inline void"),
            ("ActorSystem_CancelActor", "void"), ("ActorSystem_FillReply", "void"),
            ("ActorSystem_SequenceIsNewer", "BOOL"), ("ActorSystem_RememberReply", "void"),
            ("ActorSystem_FindReply", "const OverworldActorReply *"),
            ("OverworldActorSystem_ApplyImpl", "OverworldActorResult"),
            ("ActorSystem_RunCommand", "u16")):
        bodies.append(production_function(source, name, result).replace("static inline void", "static void", 1))
    tick = production_function(source, "OverworldActorSystem_TickImpl", "OverworldActorFrameResult")
    internal = (ROOT / "include/overworld_actor_system_internal.h").read_text()
    constant = re.findall(r"^#define OVERWORLD_ACTOR_BOUNDARY_PRESENTATION_APPLIED[^\n]*", internal, re.M)
    if len(constant) != 1:
        raise ValueError("production boundary constant differs")
    template = (ROOT / "tools/overworld/fixtures/actor_facade_commands_harness.c").read_text()
    return template.replace("/* @BODIES@ */", "\n".join(bodies)).replace("/* @TICK@ */", constant[0] + "\n" + tick)


class ActorFacadeCommandsTests(unittest.TestCase):
    def test_actual_facade_command_contract(self):
        result = execute(harness_source())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_independent_controls_reject_broken_sequence_cancel_and_queue(self):
        source = harness_source()
        for before, after, case in (("*reply = *prior;", "*reply = *prior; state->queueCount++;", "duplicate"),
                ("(s32)(sequence - reference) > 0", "sequence > reference", "wrap"),
                ("|| slot->motion.phase == OVERWORLD_MOTION_PHASE_CANCELED", "|| FALSE", "repeat cancel"),
                ("reason = ActorSystem_RunCommand(&command);", "command.expectedFieldEpoch = 0; reason = ActorSystem_RunCommand(&command);", "execution epoch")):
            with self.subTest(change=before):
                self.assertIn(before, source)
                result = execute(source.replace(before, after, 1))
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(f"actor command invariant failed: {case}:", result.stderr)


if __name__ == "__main__":
    unittest.main()
