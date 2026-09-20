#!/usr/bin/env python3
"""One disposable melonDS core, with a strict JSON-lines control channel."""

from __future__ import annotations

import os
import sys


def main():
    # Native libraries can print directly to fd 1. Keep a dedicated protocol
    # descriptor, then route both Python and native chatter to stderr BEFORE
    # importing any emulator helper.
    protocol = os.fdopen(os.dup(1), "w", buffering=1)
    os.dup2(2, 1)
    import importlib.util
    import json
    import traceback
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    expected = repo / ".venv/bin/python3"
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
            and sys.pycache_prefix == "/dev/null"):
        protocol.close()
        raise SystemExit(f"use {expected} -I -S -B -X pycache_prefix=/dev/null {__file__}")
    rt = None
    session = None
    opened = False
    for line in sys.stdin:
        request_id = None
        fatal = False
        try:
            if len(line) > 65536:
                raise ValueError("request is larger than 64 KiB")
            request = json.loads(line)
            if not isinstance(request, dict) or set(request) != {"id", "op", "args"}:
                raise ValueError("request must contain id, op, and args")
            request_id, operation, args = request["id"], request["op"], request["args"]
            if not isinstance(args, dict) or not isinstance(operation, str):
                raise ValueError("op must be a string and args an object")
            if operation == "open":
                if opened:
                    raise ValueError("a worker can open one emulator only; reset uses a new process")
                opened = True
                # Authenticate the engine-only native transport before adding
                # the repository path. No legacy scenario runner is imported.
                spec = importlib.util.spec_from_file_location(
                    "overworld_devtools_native", repo / "tools/overworld/devtools_native.py")
                native = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(native)
                sys.path.insert(0, str(repo))
                from tools.overworld import devtools_engine as rt
                rt.initialize(native)
                from tools.overworld.devtools_runtime import DevtoolsSession
                session = DevtoolsSession(rt, args["rom"], args["save"], args["sessionDir"])
                result = session.snapshot()
            else:
                if session is None or session.closed:
                    raise ValueError("open a copied session first")
                if operation == "snapshot":
                    result = session.snapshot(args.get("radius", 7))
                elif operation == "terrain":
                    result = session.terrain(args.get("radius", 7), x=args.get("x"), z=args.get("z"))
                elif operation == "step":
                    result = session.step(args.get("frames", 1), args.get("keys", []),
                                          release_at_end=args.get("releaseAtEnd", True),
                                          diagnostic_details=args.get("diagnosticDetails", True))
                elif operation == "release":
                    session.rt.h.set_key_mask(session.emu, 0)
                    result = {"released": True}
                elif operation == "diagnostics":
                    result = session.diagnostics()
                elif operation == "snapshot.probe":
                    from tools.overworld.devtools_snapshot_probe import probe_snapshot
                    result = probe_snapshot(session, args)
                elif operation == "spawn-cost.probe":
                    from tools.overworld.devtools_spawn_cost_probe import enable_spawn_cost_probe
                    result = enable_spawn_cost_probe(session, args)
                elif operation == "main-loop-pacing.arm":
                    from tools.overworld.devtools_main_loop_probe import arm_main_loop_pacing
                    result = arm_main_loop_pacing(session, args)
                elif operation == "cpu-work.start":
                    from tools.overworld.devtools_cpu_work import CPUWorkProbe
                    result = CPUWorkProbe(session, args["maxNativeFrames"]).result()
                elif operation == "cpu-work.read":
                    probe = getattr(session, "cpu_work_probe", None)
                    if probe is None:
                        raise ValueError("CPU work probe has not started")
                    result = probe.result()
                elif operation == "capture":
                    result = session.capture(args["path"])
                elif operation == "record.start":
                    result = session.record_start(args.get("maxFrames", 1800),
                                                  args.get("bindingContext", False),
                                                  role_profile=args.get("roleProfile", False))
                elif operation == "observation.prepare":
                    if args:
                        raise ValueError("observation.prepare takes no arguments")
                    result = session.prepare_observation()
                elif operation == "record.stop":
                    result = session.record_stop()
                elif operation == "observer-control.arm":
                    result = session.observer_control_arm(args)
                elif operation == "spawn-height-control.arm":
                    result = session.spawn_height_control_arm(args)
                elif operation == "observer-control.close":
                    result = session.observer_control_close()
                elif operation == "route-control.arm":
                    result = session.route_control_arm(args)
                elif operation == "chain-retry.arm":
                    result = session.chain_retry_arm(args)
                elif operation == "chain-retry.close":
                    result = session.chain_retry_close()
                elif operation == "route-control.close":
                    result = session.route_control_close()
                elif operation == "resolver.probe":
                    result = session.resolver_probe(args)
                elif operation == "condition.probe":
                    result = session.condition_probe(args)
                elif operation == "actor-inspect.probe":
                    result = session.actor_inspect_probe(args)
                elif operation == "walk-policy.reset":
                    result = session.walk_policy_reset(args)
                elif operation == "mount-walk.configure":
                    result = session.mount_walk_configure(args)
                elif operation == "mount-teleport.configure":
                    result = session.mount_teleport_configure(args)
                elif operation == "mount-teleport.restore":
                    result = session.mount_teleport_restore(args)
                elif operation == "walk-corner.arm":
                    result = session.walk_corner_arm(args)
                elif operation == "walk-matrix.arm":
                    result = session.walk_matrix_arm(args)
                elif operation == "stomp.arm":
                    result = session.stomp_arm(args)
                elif operation == "crash.arm":
                    result = session.crash_arm(args)
                elif operation == "crash.close":
                    if args:
                        raise ValueError("crash.close takes no arguments")
                    result = session.crash_close()
                elif operation == "crash.calibrate":
                    if args:
                        raise ValueError("crash.calibrate takes no arguments")
                    result = session.crash_calibrate()
                elif operation == "stomp.close":
                    if args:
                        raise ValueError("stomp.close takes no arguments")
                    result = session.stomp_close()
                elif operation == "stomp.calibrate":
                    if args:
                        raise ValueError("stomp.calibrate takes no arguments")
                    result = session.stomp_calibrate()
                elif operation == "walk-matrix.close":
                    if args:
                        raise ValueError("walk-matrix.close takes no arguments")
                    result = session.walk_matrix_close()
                elif operation == "walk-matrix.calibrate":
                    if args:
                        raise ValueError("walk-matrix.calibrate takes no arguments")
                    result = session.walk_matrix_calibrate()
                elif operation == "walk-corner.probe":
                    result = session.walk_corner_probe(args)
                elif operation == "hop-candidate.probe":
                    result = session.hop_candidate_probe(args)
                elif operation == "walk-corner.calibrate":
                    if args:
                        raise ValueError("walk-corner.calibrate takes no arguments")
                    result = session.walk_corner_calibrate()
                elif operation == "walk-corner.close":
                    if args:
                        raise ValueError("walk-corner.close takes no arguments")
                    result = session.walk_corner_close()
                elif operation == "walk-intent.arm":
                    result = session.walk_intent_arm(args)
                elif operation == "walk-policy-control.arm":
                    result = session.walk_policy_control_arm(args)
                elif operation == "mount-pacing.arm":
                    result = session.mount_pacing_arm(args)
                elif operation == "hop-arc.arm":
                    result = session.hop_arc_arm(args)
                elif operation == "wild-walk.arm":
                    result = session.wild_walk_arm(args)
                elif operation == "wild-walk.calibrate":
                    if args:
                        raise ValueError("wild-walk.calibrate takes no arguments")
                    result = session.wild_walk_calibrate()
                elif operation == "wild-walk.close":
                    if args:
                        raise ValueError("wild-walk.close takes no arguments")
                    result = session.wild_walk_close()
                elif operation == "wild-ledge.arm":
                    result = session.wild_ledge_arm(args)
                elif operation == "wild-ledge.close":
                    if args:
                        raise ValueError("wild-ledge.close takes no arguments")
                    result = session.wild_ledge_close()
                elif operation == "condition-controller.fixture":
                    result = session.condition_controller_fixture(args)
                elif operation == "condition-controller.arm":
                    result = session.condition_controller_arm(args)
                elif operation == "condition-controller.close":
                    if args:
                        raise ValueError("condition-controller.close takes no arguments")
                    result = session.condition_controller_close()
                elif operation == "mount-pacing.calibrate":
                    if args:
                        raise ValueError("mount-pacing.calibrate takes no arguments")
                    result = session.mount_pacing_calibrate()
                elif operation == "mount-pacing.close":
                    if args:
                        raise ValueError("mount-pacing.close takes no arguments")
                    result = session.mount_pacing_close()
                elif operation == "hop-arc.close":
                    if args:
                        raise ValueError("hop-arc.close takes no arguments")
                    result = session.hop_arc_close()
                elif operation == "walk-policy-control.close":
                    if args:
                        raise ValueError("walk-policy-control.close takes no arguments")
                    result = session.walk_policy_control_close()
                elif operation == "walk-intent.close":
                    if args:
                        raise ValueError("walk-intent.close takes no arguments")
                    result = session.walk_intent_close()
                elif operation in ("teleport", "spawn", "party"):
                    result = getattr(session, operation)(args)
                elif operation == "close":
                    session.close()
                    result = {"closed": True}
                else:
                    raise ValueError("unknown operation")
                # Preserve records generated by any bounded native operation,
                # not only by step. Runtime methods may already drain a batch.
                events = session.drain_events()
                if events:
                    result["events"] = result.get("events", []) + events
            response = {"id": request_id, "ok": True, "result": result}
        except Exception as error:
            traceback.print_exc(file=sys.stderr)
            fatal = bool(getattr(error, "fatal", False)) or (opened and session is None)
            response = {"id": request_id, "ok": False,
                        "error": {"code": getattr(error, "code", "invalid-request"),
                                  "message": f"{type(error).__name__}: {error}", "fatal": fatal}}
            if getattr(error, "details", None) is not None:
                response["error"]["details"] = error.details
        protocol.write(json.dumps(response, separators=(",", ":"), allow_nan=False) + "\n")
        if fatal or session is not None and session.closed:
            break
    if session is not None and not session.closed:
        session.close()
    protocol.close()


if __name__ == "__main__":
    main()
