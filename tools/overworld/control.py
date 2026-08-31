"""Implementation of the ``scripts/owctl`` host facade."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.overworld.actor_probe import (
    build_evidence_provenance,
    capture_memory_file,
    evaluate_scenario_evidence,
    load_debug_descriptor,
    load_evidence,
    require_descriptor_identity,
    require_scenario_provenance,
    write_evidence,
)
from tools.overworld.runs import make_run_manifest, utc_now, write_run_manifest
from tools.overworld.trace import decode_trace, filter_events, load_trace_schema
from tools.overworld.validation import (
    PROOF_LEVELS,
    ValidationFailure,
    cross_validate,
    load_feature_manifest,
    load_scenarios,
)


REPO = Path(__file__).resolve().parents[2]
FEATURE_MANIFEST = REPO / "tools/overworld/system_features.yaml"
SCENARIO_DIRECTORY = REPO / "tests/overworld/scenarios"
TRACE_SCHEMA = REPO / "tools/overworld/schemas/semantic-trace-v1.json"
DEBUG_DESCRIPTOR = REPO / "build/overworld-system.debug.json"


def _json(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.name


def _load_contracts() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    manifest = load_feature_manifest(FEATURE_MANIFEST)
    scenarios = load_scenarios(SCENARIO_DIRECTORY)
    cross_validate(manifest, scenarios, REPO)
    return manifest, scenarios


def _expand_command(command: list[str]) -> list[str]:
    replacements = {"{python}": sys.executable, "{repo}": str(REPO)}
    return [
        token.replace("{python}", replacements["{python}"]).replace(
            "{repo}", replacements["{repo}"]
        )
        for token in command
    ]


def _command_record(
    command: list[str], completed: subprocess.CompletedProcess[str]
) -> dict[str, Any]:
    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    return {
        "command": command,
        "returnCode": completed.returncode,
        "passed": completed.returncode == 0,
        "stdoutSha256": hashlib.sha256(stdout.encode()).hexdigest(),
        "stderrSha256": hashlib.sha256(stderr.encode()).hexdigest(),
        "stdoutTail": stdout[-2000:],
        "stderrTail": stderr[-2000:],
    }


def _run_command(command: list[str], result_kind: str) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    record = _command_record(command, completed)
    if result_kind == "json-passed" and completed.returncode == 0:
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            record["passed"] = False
            record["resultError"] = f"stdout is not JSON: {error}"
        else:
            record["passed"] = isinstance(payload, dict) and payload.get("passed") is True
            if not record["passed"]:
                record["resultError"] = "JSON result does not contain passed=true"
    return record


def _doctor(args: argparse.Namespace) -> int:
    checks: list[dict[str, Any]] = []

    def add(name: str, state: str, detail: str) -> None:
        checks.append({"name": name, "state": state, "detail": detail})

    try:
        manifest, scenarios = _load_contracts()
    except ValidationFailure as error:
        add("contracts", "error", str(error))
        manifest = None
        scenarios = {}
    else:
        add(
            "contracts",
            "ok",
            f"{len(manifest['capabilities'])} capabilities; {len(scenarios)} scenarios",
        )
    try:
        load_trace_schema(TRACE_SCHEMA)
    except ValidationFailure as error:
        add("trace-schema", "error", str(error))
    else:
        add("trace-schema", "ok", _relative(TRACE_SCHEMA))

    feature_table = subprocess.run(
        [sys.executable, "scripts/generate_overworld_feature_table.py", "--check"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    add(
        "feature-table",
        "ok" if feature_table.returncode == 0 else "error",
        (feature_table.stdout or feature_table.stderr).strip(),
    )

    if sys.version_info < (3, 10):
        add("python", "error", f"Python {sys.version_info.major}.{sys.version_info.minor} is too old")
    else:
        add("python", "ok", sys.version.split()[0])

    required_sources = [
        REPO / "scripts/verify_overworld_mount.py",
        REPO / "scripts/verify_overworld_walk_runtime.py",
        REPO / "scripts/overworld_behavior_profile_viewer.py",
    ]
    missing_sources = [_relative(path) for path in required_sources if not path.is_file()]
    add(
        "source-adapters",
        "error" if missing_sources else "ok",
        ", ".join(missing_sources) if missing_sources else "present",
    )

    optional = (
        ("rom", REPO / "test.nds"),
        ("dsv", REPO / "test.dsv"),
        ("sav", REPO / "test.sav"),
        ("build-manifest", REPO / "build/pokemon_move_history_capture_build.json"),
    )
    for name, path in optional:
        add(name, "ok" if path.is_file() else "warning", _relative(path))
    if not DEBUG_DESCRIPTOR.is_file():
        add("debug-descriptor", "warning", _relative(DEBUG_DESCRIPTOR))
    else:
        try:
            descriptor = load_debug_descriptor(DEBUG_DESCRIPTOR)
        except ValidationFailure as error:
            add("debug-descriptor", "error", str(error))
        else:
            add(
                "debug-descriptor",
                "ok",
                f"overlay {descriptor['overlay']['sha256'][:12]} facade v{descriptor['facade']['version']}",
            )
    emulator = importlib.util.find_spec("desmume")
    add(
        "emulator-python",
        "ok" if emulator is not None else "warning",
        "desmume import is available" if emulator is not None else "use the repository runtime launcher",
    )

    result = {
        "schemaVersion": 1,
        "passed": not any(check["state"] == "error" for check in checks),
        "warnings": sum(check["state"] == "warning" for check in checks),
        "checks": checks,
    }
    if args.json:
        _json(result)
    else:
        for check in checks:
            print(f"{check['state'].upper():7} {check['name']}: {check['detail']}")
        print("PASS" if result["passed"] else "FAIL")
    return 0 if result["passed"] else 1


def _scenario_list(args: argparse.Namespace) -> int:
    _, scenarios = _load_contracts()
    ordered = [scenarios[key] for key in sorted(scenarios)]
    if args.json:
        _json(
            [
                {
                    "id": item["id"],
                    "status": item["status"],
                    "proofLevel": item["proofLevel"],
                    "costTier": item["costTier"],
                    "title": item["title"],
                }
                for item in ordered
            ]
        )
    else:
        for item in ordered:
            print(
                f"{item['id']:<43} {item['status']:<7} "
                f"{item['proofLevel']}/C{item['costTier']}  {item['title']}"
            )
    return 0


def _scenario_validate(args: argparse.Namespace) -> int:
    manifest, scenarios = _load_contracts()
    if args.scenario_id and args.scenario_id not in scenarios:
        raise ValidationFailure(f"unknown scenario: {args.scenario_id}")
    selected = [args.scenario_id] if args.scenario_id else sorted(scenarios)
    result = {
        "schemaVersion": 1,
        "manifest": _relative(FEATURE_MANIFEST),
        "capabilities": len(manifest["capabilities"]),
        "scenarios": selected,
        "passed": True,
    }
    if args.json:
        _json(result)
    else:
        print(f"validated {len(selected)} scenario(s) and the feature manifest")
    return 0


def _scenario_run(args: argparse.Namespace) -> int:
    _, scenarios = _load_contracts()
    scenario = scenarios.get(args.scenario_id)
    if scenario is None:
        raise ValidationFailure(f"unknown scenario: {args.scenario_id}")
    if scenario["status"] != "active" or scenario["adapter"] is None:
        raise ValidationFailure(
            f"scenario is planned and has no truthful runtime adapter: {args.scenario_id}"
        )
    adapter = scenario["adapter"]
    if adapter["kind"] == "command-sequence":
        if args.evidence is not None:
            raise ValidationFailure("--evidence needs an actor-observation adapter")
        commands = [_expand_command(command) for command in adapter["commands"]]
    else:
        commands = []
    if args.dry_run:
        result = {
            "schemaVersion": 1,
            "scenario": args.scenario_id,
            "proofLevel": scenario["proofLevel"],
            "costTier": scenario["costTier"],
            "commands": commands,
            "evidenceRequired": adapter["kind"] == "actor-observation",
            "executed": False,
        }
        if args.json:
            _json(result)
        else:
            print(f"DRY RUN {args.scenario_id}")
            if commands:
                for command in commands:
                    print("  " + " ".join(command))
            else:
                print("  supply --evidence <actor-observation.json>")
        return 0

    started_at = utc_now()
    results = []
    if adapter["kind"] == "actor-observation":
        if args.evidence is None:
            raise ValidationFailure(
                f"scenario needs --evidence from scripts/owctl actor capture: {args.scenario_id}"
            )
        evidence_path = args.evidence if args.evidence.is_absolute() else REPO / args.evidence
        trace_schema = load_trace_schema(TRACE_SCHEMA)
        evidence = load_evidence(evidence_path, trace_schema)
        descriptor = load_debug_descriptor(DEBUG_DESCRIPTOR)
        require_descriptor_identity(evidence, descriptor)
        require_scenario_provenance(evidence, scenario, REPO)
        result = evaluate_scenario_evidence(scenario, evidence, trace_schema)
        evidence_bytes = evidence_path.read_bytes()
        result["evidence"] = {
            "path": _relative(evidence_path),
            "size": len(evidence_bytes),
            "sha256": hashlib.sha256(evidence_bytes).hexdigest(),
        }
        results.append(result)
    else:
        for command in commands:
            result = _run_command(command, adapter["result"])
            results.append(result)
            if not result["passed"]:
                break
    document = make_run_manifest(
        repo=REPO,
        kind="scenario",
        target=args.scenario_id,
        proof_level=scenario["proofLevel"],
        cost_tier=scenario["costTier"],
        scenario=scenario,
        commands=commands,
        results=results,
        started_at=started_at,
    )
    output = write_run_manifest(document, REPO, args.manifest_output)
    response = {
        "passed": document["result"]["passed"],
        "runId": document["runId"],
        "manifest": _relative(output),
        "steps": results,
    }
    if args.json:
        _json(response)
    else:
        print("PASS" if response["passed"] else "FAIL", args.scenario_id)
        print(f"manifest: {_relative(output)}")
    return 0 if response["passed"] else 1


def _trace_decode(args: argparse.Namespace) -> int:
    schema_path = args.schema if args.schema.is_absolute() else REPO / args.schema
    trace_path = args.trace if args.trace.is_absolute() else REPO / args.trace
    schema = load_trace_schema(schema_path)
    document = filter_events(
        decode_trace(trace_path, schema), args.actor, args.event
    )
    if args.json:
        _json(document)
    else:
        header = document["header"]
        print(
            f"events={len(document['events'])} fieldEpoch={header.get('fieldEpoch', '?')} "
            f"overwritten={header.get('overwrittenCount', '?')}"
        )
        for event in document["events"]:
            print(
                f"{event['sequence']:>6} f={event['frame']:<7} "
                f"actor=0x{event['actorHandle']:08X} "
                f"{event['event']:<22} {event['reason']:<18} "
                f"a={event['valueA']} b={event['valueB']}"
            )
    return 0


def _actor_source(args: argparse.Namespace) -> dict[str, Any]:
    source = args.source if args.source.is_absolute() else REPO / args.source
    data = source.read_bytes()
    schema = load_trace_schema(TRACE_SCHEMA)
    descriptor_path = (
        args.descriptor if args.descriptor.is_absolute() else REPO / args.descriptor
    )
    descriptor = load_debug_descriptor(descriptor_path)
    if data.lstrip().startswith(b"{"):
        evidence = load_evidence(source, schema)
        require_descriptor_identity(evidence, descriptor)
        return evidence
    base = args.base if args.base is not None else descriptor["state"]["address"]
    return capture_memory_file(
        source,
        base,
        descriptor,
        schema,
        include_inactive=args.include_inactive,
    )


def _actor_inspect(args: argparse.Namespace) -> int:
    evidence = _actor_source(args)
    actors = evidence["observation"]["actors"]
    if args.index is not None:
        actors = [actor for actor in actors if actor["index"] == args.index]
        if not actors:
            raise ValidationFailure(f"actor index is not present in the capture: {args.index}")
    if args.json:
        _json(
            {
                "schemaVersion": 1,
                "fieldEpoch": evidence["observation"]["fieldEpoch"],
                "actors": actors,
            }
        )
    else:
        print(
            f"fieldEpoch={evidence['observation']['fieldEpoch']} actors={len(actors)}"
        )
        for actor in actors:
            handle = actor["handle"]
            print(
                f"[{actor['index']:>2}] 0x{handle['value']:08X} "
                f"{actor['role']:<9} species={actor['species']:<3} "
                f"motion={actor['motionKind']}/{actor['motionPhase']} "
                f"logical=({actor['logical']['x']},{actor['logical']['y']}) "
                f"render=({actor['render']['x']},{actor['render']['y']}) "
                f"input={actor['inputOwnership']} commit={actor['commitSequence']}"
            )
    return 0


def _actor_trace(args: argparse.Namespace) -> int:
    evidence = _actor_source(args)
    document = filter_events(
        evidence["observation"]["trace"], args.actor, args.event
    )
    if args.json:
        _json(document)
    else:
        header = document["header"]
        print(
            f"events={len(document['events'])} fieldEpoch={header['fieldEpoch']} "
            f"overwritten={header['overwrittenCount']}"
        )
        for event in document["events"]:
            print(
                f"{event['sequence']:>6} f={event['frame']:<7} "
                f"actor=0x{event['actorHandle']:08X} "
                f"{event['event']:<22} {event['reason']:<18} "
                f"a={event['valueA']} b={event['valueB']}"
            )
    return 0


def _actor_capture(args: argparse.Namespace) -> int:
    source = args.source if args.source.is_absolute() else REPO / args.source
    descriptor_path = (
        args.descriptor if args.descriptor.is_absolute() else REPO / args.descriptor
    )
    descriptor = load_debug_descriptor(descriptor_path)
    schema = load_trace_schema(TRACE_SCHEMA)
    base = args.base if args.base is not None else descriptor["state"]["address"]
    provenance = None
    provenance_arguments = (args.scenario_id, args.rom, args.save, args.seed)
    if any(value is not None for value in provenance_arguments):
        if args.scenario_id is None or args.rom is None or args.seed is None:
            raise ValidationFailure(
                "reusable evidence provenance needs --scenario-id, --rom, and --seed"
            )
        rom = args.rom if args.rom is None or args.rom.is_absolute() else REPO / args.rom
        save = (
            args.save if args.save is None or args.save.is_absolute() else REPO / args.save
        )
        provenance = build_evidence_provenance(
            scenario_id=args.scenario_id,
            rom=rom,
            save=save,
            seed=args.seed,
        )
    if args.output is not None and provenance is None:
        raise ValidationFailure(
            "reusable evidence output needs explicit --scenario-id, --rom, and --seed provenance"
        )
    evidence = capture_memory_file(
        source,
        base,
        descriptor,
        schema,
        include_inactive=args.include_inactive,
        provenance=provenance,
    )
    if args.output is None:
        _json(evidence)
    else:
        output = args.output if args.output.is_absolute() else REPO / args.output
        write_evidence(evidence, output)
        print(_relative(output))
    return 0


def _add_actor_source_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("source", type=Path, help="Actor evidence or raw memory dump")
    parser.add_argument(
        "--descriptor", type=Path, default=DEBUG_DESCRIPTOR, help="Generated debug descriptor"
    )
    parser.add_argument("--base", type=lambda value: int(value, 0))
    parser.add_argument("--include-inactive", action="store_true")


def _git_changed_paths(base: str | None) -> list[str]:
    commands = []
    if base:
        commands.append(["git", "diff", "--name-only", f"{base}...HEAD", "--"])
    commands.append(["git", "diff", "--name-only", "HEAD", "--"])
    paths: set[str] = set()
    for command in commands:
        completed = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
        if completed.returncode != 0:
            raise ValidationFailure(completed.stderr.strip() or "git diff failed")
        paths.update(line for line in completed.stdout.splitlines() if line)
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    if untracked.returncode != 0:
        raise ValidationFailure(untracked.stderr.strip() or "git ls-files failed")
    paths.update(line for line in untracked.stdout.splitlines() if line)
    return sorted(paths)


def _matches(path: str, patterns: list[str]) -> bool:
    from fnmatch import fnmatch

    return any(fnmatch(path, pattern) for pattern in patterns)


def _requirement_state(requirement: str) -> tuple[bool, str]:
    paths = {
        "rom": REPO / "test.nds",
        "dsv": REPO / "test.dsv",
        "sav": REPO / "test.sav",
        "debugDescriptor": REPO / "build/overworld-system.debug.json",
    }
    if requirement == "source":
        return True, "source"
    if requirement == "build":
        required = (
            REPO / "build/overworld_mount_overlay_linked.o",
            REPO / "build/overworld_wild_spawns_overlay_linked.o",
            REPO / "build/overworld_wild_runtime_overlay_linked.o",
            REPO / "build/pokemon_move_history_task6_overlay_linked.o",
        )
        missing = [_relative(path) for path in required if not path.is_file()]
        return not missing, "linked objects" if not missing else ", ".join(missing)
    if requirement == "emulator":
        present = importlib.util.find_spec("desmume") is not None
        return present, "desmume import"
    path = paths[requirement]
    return path.is_file(), _relative(path)


def _verify_affected(args: argparse.Namespace) -> int:
    manifest, _ = _load_contracts()
    paths = sorted(set(args.path or _git_changed_paths(args.base)))
    if not paths:
        raise ValidationFailure("no affected paths; pass --path or --base")
    check_by_id = {check["id"]: check for check in manifest["checks"]}
    selected_ids: set[str] = set()
    capability_hits = []
    for capability in manifest["capabilities"]:
        matched = [
            path for path in paths if _matches(path, capability["sourcePatterns"])
        ]
        if matched:
            capability_hits.append({"id": capability["id"], "paths": matched})
            selected_ids.update(capability["checks"])
    for check in manifest["checks"]:
        if any(_matches(path, check["sourcePatterns"]) for path in paths):
            selected_ids.add(check["id"])
    if not selected_ids:
        raise ValidationFailure(
            "affected paths have no feature-map owner: " + ", ".join(paths)
        )
    selected = sorted(
        (check_by_id[check_id] for check_id in selected_ids),
        key=lambda check: (
            check["costTier"],
            PROOF_LEVELS.index(check["proofLevel"]),
            check["id"],
        ),
    )
    plan = []
    for check in selected:
        requirements = []
        ready = True
        for requirement in check["requires"]:
            present, detail = _requirement_state(requirement)
            requirements.append(
                {"name": requirement, "present": present, "detail": detail}
            )
            ready &= present
        plan.append(
            {
                "id": check["id"],
                "title": check["title"],
                "proofLevel": check["proofLevel"],
                "costTier": check["costTier"],
                "command": _expand_command(check["command"]),
                "requirements": requirements,
                "ready": ready,
            }
        )

    if not args.run:
        result = {
            "schemaVersion": 1,
            "executed": False,
            "paths": paths,
            "capabilities": capability_hits,
            "checks": plan,
        }
        if args.json:
            _json(result)
        else:
            print("DRY RUN: cheapest checks are listed first")
            for check in plan:
                state = "READY" if check["ready"] else "MISSING INPUT"
                print(
                    f"C{check['costTier']} {check['proofLevel']} {state:<13} {check['id']}"
                )
                print("  " + " ".join(check["command"]))
            print("Use --run to execute this exact plan.")
        return 0

    not_ready = [check for check in plan if not check["ready"]]
    if not_ready:
        detail = "; ".join(
            f"{check['id']}: "
            + ", ".join(
                item["name"] for item in check["requirements"] if not item["present"]
            )
            for check in not_ready
        )
        raise ValidationFailure("affected verification inputs are missing: " + detail)

    started_at = utc_now()
    results = []
    commands = []
    for check in plan:
        commands.append(check["command"])
        result = _run_command(check["command"], "exit-zero")
        result["checkId"] = check["id"]
        results.append(result)
        if not result["passed"]:
            break
    highest_proof = max(
        (check["proofLevel"] for check in selected),
        key=PROOF_LEVELS.index,
    )
    document = make_run_manifest(
        repo=REPO,
        kind="affected-verification",
        target="affected-" + hashlib.sha256("\n".join(paths).encode()).hexdigest()[:12],
        proof_level=highest_proof,
        cost_tier=max(check["costTier"] for check in selected),
        scenario=None,
        commands=commands,
        results=results,
        started_at=started_at,
    )
    output = write_run_manifest(document, REPO, args.manifest_output)
    response = {
        "passed": document["result"]["passed"],
        "runId": document["runId"],
        "manifest": _relative(output),
        "steps": results,
    }
    if args.json:
        _json(response)
    else:
        print("PASS" if response["passed"] else "FAIL", "affected verification")
        print(f"manifest: {_relative(output)}")
    return 0 if response["passed"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scripts/owctl",
        description="Inspect and verify the overworld actor system.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    doctor = commands.add_parser("doctor", help="Check host-control readiness")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(handler=_doctor)

    scenario = commands.add_parser("scenario", help="List, validate, or run scenarios")
    scenario_commands = scenario.add_subparsers(dest="scenario_command", required=True)
    scenario_list = scenario_commands.add_parser("list")
    scenario_list.add_argument("--json", action="store_true")
    scenario_list.set_defaults(handler=_scenario_list)
    scenario_validate = scenario_commands.add_parser("validate")
    scenario_validate.add_argument("scenario_id", nargs="?")
    scenario_validate.add_argument("--json", action="store_true")
    scenario_validate.set_defaults(handler=_scenario_validate)
    scenario_run = scenario_commands.add_parser("run")
    scenario_run.add_argument("scenario_id")
    scenario_run.add_argument("--dry-run", action="store_true")
    scenario_run.add_argument("--evidence", type=Path)
    scenario_run.add_argument("--json", action="store_true")
    scenario_run.add_argument("--manifest-output", type=Path)
    scenario_run.set_defaults(handler=_scenario_run)

    trace = commands.add_parser("trace", help="Decode a semantic trace")
    trace_commands = trace.add_subparsers(dest="trace_command", required=True)
    trace_decode = trace_commands.add_parser("decode")
    trace_decode.add_argument("trace", type=Path)
    trace_decode.add_argument("--schema", type=Path, default=TRACE_SCHEMA)
    trace_decode.add_argument("--actor", type=lambda value: int(value, 0))
    trace_decode.add_argument("--event")
    trace_decode.add_argument("--json", action="store_true")
    trace_decode.set_defaults(handler=_trace_decode)

    actor = commands.add_parser("actor", help="Inspect public actor observation")
    actor_commands = actor.add_subparsers(dest="actor_command", required=True)
    actor_inspect = actor_commands.add_parser("inspect", help="Inspect actor snapshots")
    _add_actor_source_arguments(actor_inspect)
    actor_inspect.add_argument("--index", type=int)
    actor_inspect.add_argument("--json", action="store_true")
    actor_inspect.set_defaults(handler=_actor_inspect)
    actor_trace = actor_commands.add_parser("trace", help="Inspect actor semantic trace")
    _add_actor_source_arguments(actor_trace)
    actor_trace.add_argument("--actor", type=lambda value: int(value, 0))
    actor_trace.add_argument("--event")
    actor_trace.add_argument("--json", action="store_true")
    actor_trace.set_defaults(handler=_actor_trace)
    actor_capture = actor_commands.add_parser(
        "capture", help="Create reusable actor observation evidence"
    )
    _add_actor_source_arguments(actor_capture)
    actor_capture.add_argument("--scenario-id")
    actor_capture.add_argument("--rom", type=Path)
    actor_capture.add_argument("--save", type=Path)
    actor_capture.add_argument("--seed", type=lambda value: int(value, 0))
    actor_capture.add_argument("--output", type=Path)
    actor_capture.set_defaults(handler=_actor_capture)

    verify = commands.add_parser("verify", help="Select proof from the feature map")
    verify_commands = verify.add_subparsers(dest="verify_command", required=True)
    affected = verify_commands.add_parser("affected")
    affected.add_argument("--base")
    affected.add_argument("--path", action="append")
    affected.add_argument("--run", action="store_true")
    affected.add_argument("--json", action="store_true")
    affected.add_argument("--manifest-output", type=Path)
    affected.set_defaults(handler=_verify_affected)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except ValidationFailure as error:
        print(f"owctl: {error}", file=sys.stderr)
        return 2
    except FileNotFoundError as error:
        print(f"owctl: missing file: {error.filename}", file=sys.stderr)
        return 2
