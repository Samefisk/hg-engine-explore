#!/usr/bin/env python3
"""Small production-C Cargo setup checks, with the real resumable reducer.

Only native structs/callbacks are host fixtures. Scope's three native pointer
offsets are mapped to host pointer-width storage; slot +860/+864 stay exact.
This is setup/cache proof, not ARM layout, loader lifetime or game pacing proof.
"""
from pathlib import Path
import argparse
import hashlib
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "lib/overworld/overworld_cargo_query_wild.c"
FIXTURE = ROOT / "tools/overworld/fixtures/cargo_query_wild_harness.c"


def host_body(source):
    body = re.sub(r'^#include "[^"]+"\n', '', source, flags=re.MULTILINE)
    # This named macro is part of production policy. Keep it exact while the
    # fixture substitutes only the native engine structs used below.
    header = (ROOT / "include/overworld_wild_behavior_data.h").read_text()
    macros = re.findall(r'^#define OW_WILD_BEHAVIOR_SKID_BOOLEAN\(options\).*$', header, re.MULTILINE)
    if len(macros) != 1:
        raise SystemExit("production packed boolean declaration changed")
    body = macros[0] + "\n" + body
    for name in ("CARGO_TARGET_CHECK_INTERVAL", "CARGO_TARGET_SWITCH_ADVANTAGE"):
        matches = re.findall(r'^#define OW_WILD_BEHAVIOR_' + name + r'\(options\).*$', header, re.MULTILINE)
        if len(matches) != 1:
            raise SystemExit("production Cargo profile declaration changed: " + name)
        body = matches[0] + "\n" + body
    # Native ABI has four 32-bit pointers. Host pointers need separate space;
    # these substitutions adapt storage only, preserving the production loop.
    seams = {
        '((u8 *)world->field+0x2C)': '((u8 *)world->field+offsetof(FieldSystem, land))',
        '(land+0x90+4*i)': '(land+0x90+sizeof(void *)*i)',
        'land[0xA0]': 'land[0xC0]',
    }
    for old, new in seams.items():
        if body.count(old) != 1:
            raise SystemExit("native host storage seam changed: " + old)
        body = body.replace(old, new)
    return body


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slot-mask-red", action="store_true",
                        help="run only the retained native slot/compact mask regression")
    parser.add_argument("--follower-priority-only", action="store_true",
                        help="run only current exact-Interest query ownership controls")
    parser.add_argument("--wild-resource-limit-only", action="store_true",
                        help="run only grounded Wild owner release after real route storage exhaustion")
    parser.add_argument("--wild-unreachable-only", action="store_true",
                        help="run only natural enclosed-Wild release to reachable peer Cargo and copied failure controls")
    parser.add_argument("--unavailable-cargo-only", action="store_true",
                        help="run only unavailable exact-Interest/empty-Cargo reads beside a protected foreign workspace")
    parser.add_argument("--wild-retarget-only", action="store_true",
                        help="run current nearest-Cargo interval and Cargo-only owner release checks")
    args = parser.parse_args()
    cc = shutil.which("cc")
    if not cc:
        raise SystemExit("host C compiler required")
    source = SOURCE.read_text()
    native_header = (ROOT / "include/overworld_wild_behavior_data.h").read_text()
    for name, value in (("CARDINAL_ONLY", 0), ("CARDINAL_AND_DIAGONAL", 1), ("DIAGONAL_ONLY", 2)):
        if not re.search(r'^#define OW_WILD_BEHAVIOR_MOVEMENT_DIRECTIONS_' + name + r' ' + str(value) + r'$', native_header, re.MULTILINE):
            raise SystemExit("authored native direction values changed: " + name)
    with tempfile.TemporaryDirectory(prefix="cargo-wild-") as temporary:
        directory = Path(temporary)
        production = directory / "cargo_query_wild_production.inc"
        production.write_text(host_body(source))
        read_source = (ROOT / "lib/overworld/overworld_cargo_read_wild.c").read_text()
        start = read_source.index("u32 OverworldCargoReadWild_Observe(")
        end = read_source.index("\nconst OverworldActorSystemState *", start)
        (directory / "cargo_read_wild_observe_production.inc").write_text(read_source[start:end])
        held_source = (ROOT / "lib/overworld/overworld_throw_held_wild.c").read_text()
        start = held_source.index("BOOL OverworldThrowHeldWild_ReleaseCargo(")
        end = held_source.index("\n/* The shared held intent", start)
        (directory / "cargo_release_production.inc").write_text(held_source[start:end])
        prepared_header = (ROOT / "include/overworld_behavior_condition_runtime.h").read_text()
        start = prepared_header.index("typedef struct OverworldBehaviorConditionPreparedActor {")
        end = prepared_header.index("} OverworldBehaviorConditionPreparedActor;", start) + len("} OverworldBehaviorConditionPreparedActor;")
        (directory / "cargo_prepared_production.inc").write_text(prepared_header[start:end])
        motion = (ROOT / "include/overworld_motion_model.h").read_text()
        decision = motion[motion.index("typedef enum OverworldMotionDecision {"):motion.index("} OverworldMotionDecision;") + len("} OverworldMotionDecision;")]
        phase = motion[motion.index("typedef enum OverworldMotionPhase {"):motion.index("} OverworldMotionPhase;") + len("} OverworldMotionPhase;")]
        (directory / "cargo_motion_decision_production.inc").write_text(phase + "\n" + decision + "\n")
        route_source = (ROOT / "lib/overworld/overworld_pickup_route_wild.c").read_text()
        def function(name):
            start = route_source.index("static " + ("int " if name == "Abs" else "Result ") + name + "(")
            brace = route_source.index("{", start)
            end, depth = brace + 1, 1
            while depth:
                depth += (route_source[end] == "{") - (route_source[end] == "}")
                end += 1
            return route_source[start:end] + "\n"
        (directory / "cargo_walk_policy_production.inc").write_text(function("Abs") + function("EdgePolicy"))
        binary = directory / "check"
        command = [cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                   "-Wno-misleading-indentation", "-DOVERWORLD_ACTOR_SYSTEM_HOST",
                   "-I", str(ROOT / "include"), "-I", str(directory)]
        sources = [ROOT / ("lib/overworld/" + name) for name in (
            "overworld_cargo_query.c", "overworld_pickup_route.c", "overworld_pickup_route_native.c")]
        compile_command = command + [str(FIXTURE), *map(str, sources), "-o", str(binary)]
        subprocess.run(compile_command, check=True)
        if args.wild_retarget_only:
            raise SystemExit(subprocess.run([str(binary), "--wild-retarget-regression"]).returncode)
        if args.unavailable_cargo_only:
            for file in (SOURCE, ROOT / "lib/overworld/overworld_cargo_read_wild.c", FIXTURE, Path(__file__)):
                print(file.relative_to(ROOT), hashlib.sha256(file.read_bytes()).hexdigest(), flush=True)
            raise SystemExit(subprocess.run([str(binary), "--unavailable-cargo-regression"]).returncode)
        def unreachable_controls():
            read_production = directory / "cargo_read_wild_observe_production.inc"
            original_read = read_production.read_text()
            controls = (
                ("unreachable workspace handoff omitted", "query",
                 "priority=idle && (((q->cached.status==LIMIT || q->cached.status==UNREACHABLE)",
                 "priority=idle && (((q->cached.status==LIMIT)",
                 "q->valid && Same(&q->owner,&actors.slots[2].snapshot.handle,12)"),
                ("unreachable Interest abort omitted", "read",
                 "\n                        || status == OVERWORLD_PICKUP_ROUTE_UNREACHABLE", "",
                 "abort && !observation"),
                ("handoff frame budget discarded", "query",
                 "q->state.frame=frame;q->state.frameValid=frameValid;",
                 "(void)frame;(void)frameValid;", "nativeCalls==terminalCalls"),
            )
            for name, target, old, new, expected in controls:
                original = source if target == "query" else original_read
                if original.count(old) != 1:
                    raise SystemExit("production control boundary changed: " + name)
                production.write_text(host_body(source.replace(old, new) if target == "query" else source))
                read_production.write_text(original_read.replace(old, new) if target == "read" else original_read)
                subprocess.run(compile_command, check=True)
                result = subprocess.run([str(binary), "--wild-unreachable-regression"], capture_output=True, text=True)
                if result.returncode == 0 or expected not in result.stderr:
                    raise SystemExit("failed to reject intended control: " + name + "\n" + result.stdout + result.stderr)
                print("rejected control:", name, flush=True)
            production.write_text(host_body(source))
            read_production.write_text(original_read)

        if args.wild_unreachable_only:
            subprocess.run([str(binary), "--wild-unreachable-regression"], check=True)
            unreachable_controls()
            for file in (SOURCE, ROOT / "lib/overworld/overworld_cargo_read_wild.c", FIXTURE, Path(__file__)):
                print(file.relative_to(ROOT), hashlib.sha256(file.read_bytes()).hexdigest())
            return
        if args.follower_priority_only:
            raise SystemExit(subprocess.run([str(binary), "--follower-priority-regression"]).returncode)
        if args.wild_resource_limit_only:
            for file in (SOURCE, FIXTURE, Path(__file__)):
                print(file.relative_to(ROOT), hashlib.sha256(file.read_bytes()).hexdigest(), flush=True)
            raise SystemExit(subprocess.run([str(binary), "--wild-resource-limit-regression"]).returncode)
        if args.slot_mask_red:
            # Authenticate the native input and compact-list contracts used by
            # this production bridge receipt; these are not guessed masks.
            observation = (ROOT / "lib/overworld/overworld_throw_observation_native.c").read_text()
            adapter = (ROOT / "lib/overworld/overworld_behavior_condition_adapter.c").read_text()
            for text, anchor in ((observation, "u16 candidateMask = PLAYER_HEALTH_THROW_SLOT_MASK(i);"),
                                 (observation, "cargoMask |= candidateMask;"),
                                 (observation, "((u32)cargoMask << 8)"),
                                 (adapter, "index = frame->world.actorCount;"),
                                 (adapter, "frame->world.actorCount++;")):
                if anchor not in text:
                    raise SystemExit("native slot/compact contract changed: " + anchor)
            for file in (SOURCE, FIXTURE, Path(__file__)):
                print(file.relative_to(ROOT), hashlib.sha256(file.read_bytes()).hexdigest(), flush=True)
            raise SystemExit(subprocess.run([str(binary), "--slot-mask-regression"]).returncode)
        subprocess.run([str(binary)], check=True)
        unreachable_controls()
        # One small control per reported setup fault. Reducers stay unchanged;
        # each production setup mutation must fail its real receipt assertion.
        mutants = {
            "Walk modeled as Hop": (
                'u8 hop=call->locomotion==OW_WILD_BEHAVIOR_LOCOMOTION_HOP;',
                'u8 hop=call->locomotion==OW_WILD_BEHAVIOR_LOCOMOTION_HOP || (call->locomotion==OW_WILD_BEHAVIOR_LOCOMOTION_WALK && OW_WILD_BEHAVIOR_MOVEMENT_ALLOWS_DIAGONAL(mode));'),
            "absolute range anchor resets moving graph": (
                "hash=Hash(hash,subject->xrange==-1?0:subject->xInit-anchorX);\n    hash=Hash(hash,subject->yrange==-1?0:subject->yInit-anchorY);",
                "(void)anchorX;(void)anchorY;hash=Hash(hash,subject->xInit);hash=Hash(hash,subject->yInit);"),
            "unlimited Hop midpoint resets policy": (
                "hash=Hash(hash,subject->xrange==-1?0:subject->xInit-anchorX);\n    hash=Hash(hash,subject->yrange==-1?0:subject->yInit-anchorY);",
                "hash=Hash(hash,subject->xInit-anchorX);hash=Hash(hash,subject->yInit-anchorY);"),
            "irrelevant Hop fields reset Walk policy": ('if(hop) {', 'if(1) {'),
            "relevant Hop timing omitted": ('hash=Hash(hash,lane->hopTime);', ''),
            "native policy flag omitted": ('hash=Hash(hash,subject->flags2&(1u<<2));', ''),
            "object reuse identity omitted": ('now.identity=object->id;', ''),
            "last evaluated subject reused": ('view.subject=bindings->subject;', 'view.subject=conditions->frame.world.subject;'),
            "same-frame native observations skipped": ('q->frame=frame;', 'if(q->valid && q->frame==frame)return 1;q->frame=frame;'),
            "stale self falsely omitted": ('&& CurrentActor(world,actors,subject)', '&& 1'),
            "wrong self object falsely omitted": ('&& world->subjectObject==world->state->spawns[world->slot].object;', '&& 1;'),
        }
        for name, (old, new) in mutants.items():
            if source.count(old) != 1:
                raise SystemExit("production control boundary changed: " + name)
            production.write_text(host_body(source.replace(old, new)))
            subprocess.run(command + [str(FIXTURE), *map(str, sources), "-o", str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            if result.returncode == 0:
                raise SystemExit("failed to reject control: " + name)
            print("rejected control:", name)
    for file in (SOURCE, ROOT / "lib/overworld/overworld_cargo_read_wild.c", ROOT / "include/overworld_cargo_query_wild.h", FIXTURE, Path(__file__)):
        print(file.relative_to(ROOT), hashlib.sha256(file.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
