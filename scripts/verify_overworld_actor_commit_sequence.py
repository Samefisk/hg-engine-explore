#!/usr/bin/env python3
"""S1: actual actor commit body plus the real portable motion model.

World publication, tracing, and Walk COMMIT reduction use host stubs. Policy
INSPECT, chain readiness, and reservation release use production bodies. This
is not ARM ABI, packaged ROM, or gameplay proof.
"""
from pathlib import Path
import importlib.util
import os
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ACTOR = ROOT / "src/overworld_actor_system_overlay/overworld_actor_system_overlay.c"
FIXTURE = ROOT / "tools/overworld/fixtures/actor_commit_sequence_harness.c"


def harness_source():
    spec = importlib.util.spec_from_file_location("actor_commit_extract", ROOT / "scripts/verify_overworld_spawn_profile_lifecycle.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    internal = (ROOT / "include/overworld_actor_system_internal.h").read_text()
    movement = (ROOT / "include/overworld_wild_movement.h").read_text()
    wild = (ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
    runtime = (ROOT / "src/overworld_wild_runtime_overlay/overworld_wild_runtime_overlay.c").read_text()
    declarations = []
    for header, kind, name in (
        (movement, "struct", "OverworldWildWalkMomentumState"),
        (movement, "enum", "OverworldActorWalkPolicyOperation"),
        (movement, "enum", "OverworldActorWalkPolicyDecision"),
        (movement, "struct", "OverworldActorPolicyView"),
        (movement, "struct", "OverworldActorWalkPolicyCall"),
    ):
        matches = re.findall(r"typedef " + kind + " " + name + r"\s*\{[\s\S]*?\}\s*" + name + ";", header)
        if len(matches) != 1:
            raise ValueError("production declaration differs: " + name)
        declarations.append(matches[0])
    matches = re.findall(r"struct OverworldActorPolicyState\s*\{[^}]+\};", internal)
    if len(matches) != 1:
        raise ValueError("production policy state differs")
    declarations += ["typedef struct OverworldActorPolicyState OverworldActorPolicyState;", matches[0]]
    runtime_slots = re.findall(
        r"typedef struct OverworldActorRuntimeSlot\s*\{[\s\S]*?\}\s*OverworldActorRuntimeSlot;",
        internal,
    )
    if len(runtime_slots) != 1:
        raise ValueError("production declaration differs: OverworldActorRuntimeSlot")
    declarations.append(runtime_slots[0])
    definitions = dict((name, line) for line, name in re.findall(
        r"^(#define\s+([A-Za-z_]\w*)[^\n]*)$", (internal + "\n" + movement).replace("\\\n", " "), re.M))
    needed = set()
    def constant(name):
        if name in needed:
            return
        if name not in definitions:
            raise ValueError("production macro differs: " + name)
        needed.add(name)
        for token in re.findall(r"\bOVERWORLD_[A-Z_0-9]+\b", definitions[name].split(name, 1)[1]):
            constant(token)
    for name in ("OVERWORLD_ACTOR_BOUNDARY_REQUIRED_ACKS", "OVERWORLD_ACTOR_WALK_POLICY_VERSION",
                 "OVERWORLD_ACTOR_WALK_PENDING_NONE", "OVERWORLD_ACTOR_WALK_PENDING_CHAIN",
                 "OVERWORLD_ACTOR_WALK_STEP_SKID"):
        constant(name)
    source = FIXTURE.read_text()
    # Use the real INSPECT switch arm; other reducer operations are outside
    # this bounded publication test and retain the explicit COMMIT stub.
    apply_command = helper.production_function(runtime, "OverworldActorWalkPolicy_ApplyCommand", "BOOL")
    inspect_arms = re.findall(
        r"case OVERWORLD_ACTOR_WALK_POLICY_INSPECT:\s*([\s\S]*?)"
        r"(?=\s*case OVERWORLD_ACTOR_WALK_POLICY_BIND_PROFILE:)", apply_command)
    if len(inspect_arms) != 1:
        raise ValueError("production policy INSPECT arm differs")
    inspect_inline = re.sub(r"\bstatic inline BOOL\b", "static BOOL", internal)
    replacements = {
        "/* @DECLARATIONS@ */": "\n".join(declarations),
        "/* @CONSTANTS@ */": "\n".join(definitions[name] for name in sorted(needed)),
        "/* @ACKNOWLEDGE@ */": helper.production_function(ACTOR.read_text(), "ActorSystem_TryAcknowledgeMotionCommit", "OverworldMotionDecision"),
        "/* @RELEASE_TARGET@ */": helper.production_function(ACTOR.read_text(), "ActorSystem_ReleaseTarget", "inline void").replace("static inline void", "static void", 1),
        "/* @INSPECT_ARM@ */": inspect_arms[0],
        "/* @INSPECT@ */": helper.production_function(inspect_inline, "OverworldActorPolicy_Inspect", "BOOL"),
        "/* @CHAIN_READY@ */": helper.production_function(wild, "OverworldWildSpawns_IsChainActionReady", "BOOL"),
    }
    for marker, value in replacements.items():
        if source.count(marker) != 1:
            raise ValueError("fixture marker differs: " + marker)
        source = source.replace(marker, value)
    return source


def execute(source):
    with tempfile.TemporaryDirectory(prefix="actor-commit-sequence-") as directory:
        temporary = Path(directory)
        unit, binary = temporary / "commit.c", temporary / "commit"
        unit.write_text(source)
        command = [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11", "-O2",
                   "-Wall", "-Wextra", "-Werror", "-DOVERWORLD_ACTOR_SYSTEM_HOST",
                   "-DOVERWORLD_MOTION_HOST", "-I", str(ROOT / "include"), str(unit),
                   str(ROOT / "lib/overworld/overworld_motion_model.c"), "-o", str(binary)]
        compiled = subprocess.run(command, capture_output=True, text=True)
        if compiled.returncode:
            raise RuntimeError("actor commit host compile failed:\n" + compiled.stderr)
        return subprocess.run([str(binary)], capture_output=True, text=True)


def main():
    source = harness_source()
    baseline = execute(source)
    print(baseline.stdout + baseline.stderr, end="")
    if baseline.returncode:
        return 1
    mutations = {
        "per-motion counter assignment": ("actor->commitSequence++;", "actor->commitSequence = motion->commitSequence;"),
        "16-bit actor truncation": ("actor->commitSequence++;", "actor->commitSequence = (u16)(actor->commitSequence + 1);"),
        "double publication count": ("actor->commitSequence++;", "actor->commitSequence += 2;"),
        "advance on rejected acknowledgement": (
            "if (decision != OVERWORLD_MOTION_DECISION_ACCEPTED) {",
            "if (decision != OVERWORLD_MOTION_DECISION_ACCEPTED) { actor->commitSequence++;"),
        "missing engine-END guard": (
            "& OVERWORLD_ACTOR_BOUNDARY_REQUIRED_ACKS)\n            != OVERWORLD_ACTOR_BOUNDARY_REQUIRED_ACKS",
            "& (OVERWORLD_ACTOR_BOUNDARY_REQUIRED_ACKS & ~OVERWORLD_ACTOR_BOUNDARY_ENGINE_END))\n"
            "            != (OVERWORLD_ACTOR_BOUNDARY_REQUIRED_ACKS & ~OVERWORLD_ACTOR_BOUNDARY_ENGINE_END)"),
        "stale public terminal phase": (
            "actor->motionPhase = motion->phase;", "/* Public phase was not refreshed. */"),
        "settling reported as idle": (
            "actor->motionPhase = motion->phase;", "actor->motionPhase = OVERWORLD_MOTION_PHASE_IDLE;"),
        "stale terminal motion kind": (
            "actor->motionKind = OVERWORLD_ACTOR_MOTION_NONE;", "/* Old motion kind was retained. */"),
        "stale terminal stream phase": (
            "actor->streamState = OVERWORLD_ACTOR_STREAM_IDLE;", "/* Old stream phase was retained. */"),
        "motion completion clears role input ownership": (
            "actor->motionPhase = motion->phase;", "actor->motionPhase = motion->phase; actor->inputOwnership = 0;"),
        "INSPECT reports stale phase": (
            "call->policyView->motionPhase = actor->motionPhase;",
            "call->policyView->motionPhase = OVERWORLD_MOTION_PHASE_COMMIT_PENDING;"),
    }
    for label, (old, new) in mutations.items():
        if source.count(old) != 1:
            raise ValueError("production mutation seam differs: " + label)
        mutant = execute(source.replace(old, new))
        if mutant.returncode != 1 or "actor commit invariant failed" not in mutant.stderr:
            raise RuntimeError("known-bad actor commit was not rejected: " + label)
        print("PASS known-bad actor commit rejected: " + label)
    print("PASS S1 actor lifetime commit sequence and same-boundary public terminal state; engine stubs, no gameplay claim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
