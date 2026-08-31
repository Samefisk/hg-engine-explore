"""Strict validators for overworld host-control data."""

from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path
from typing import Any, Iterable


ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
PROOF_LEVELS = ("S0", "S1", "S2", "S3", "S4", "S5")
ROLES = ("Wild", "Follower", "Mounted", "Scripted")
REQUIREMENTS = (
    "source",
    "build",
    "rom",
    "dsv",
    "sav",
    "emulator",
    "debugDescriptor",
)
TRACE_GROUPS = (
    "actor",
    "profile",
    "intent",
    "motion",
    "streaming",
    "presentation",
    "lifecycle",
    "population",
)
SCENARIO_STATUSES = ("active", "planned")
CAPTURE_POLICIES = ("none", "failure", "always")
EVENT_KINDS = ("input", "lifecycle", "setup")
RESULT_KINDS = ("exit-zero", "json-passed")
ACTOR_SEMANTIC_CHECKS = (
    "trace-window-complete",
    "terminal-result",
    "no-commit-after-cancel",
    "control-returned",
    "single-motion-owner",
    "field-epoch-current",
    "presentation-attached",
)
ACTOR_INVARIANT_CHECKS = {
    "Each accepted motion has exactly one terminal result": ("terminal-result",),
    "No logical commit occurs after motion cancellation": (
        "no-commit-after-cancel",
    ),
    "Control returns after the selected motion finishes or cancels": (
        "control-returned",
    ),
    "No active actors share a nonzero target reservation": (
        "single-motion-owner",
    ),
    "Every active actor handle uses the current field epoch": (
        "field-epoch-current",
    ),
    "Every active actor has an attached presentation": (
        "presentation-attached",
    ),
}
SEMANTIC_EVENTS = (
    "ACTOR_ATTACHED",
    "ACTOR_DETACHED",
    "CONTROL_REBOUND",
    "PROFILE_RESOLVED",
    "LANE_CHANGED",
    "INTENT_CREATED",
    "CANDIDATE_REJECTED",
    "PLAN_ACCEPTED",
    "MOTION_STARTED",
    "STREAM_WAITING",
    "STREAM_ADVANCED",
    "PATH_ADVANCED",
    "LOGICAL_COMMIT",
    "WORLD_EFFECT",
    "PRESENTATION_SYNCED",
    "MOTION_FINISHED",
    "MOTION_CANCELED",
    "CONTEXT_CHANGED",
    "ACTOR_REBOUND",
    "CONTROL_RETURNED",
)


class ValidationFailure(ValueError):
    """Raised when a strict control document is invalid."""


def load_json_document(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as error:
        raise ValidationFailure(f"missing file: {path}") from error
    except json.JSONDecodeError as error:
        raise ValidationFailure(
            f"{path}:{error.lineno}:{error.colno}: invalid JSON: {error.msg}"
        ) from error


def _fail(errors: list[str], location: str, message: str) -> None:
    errors.append(f"{location}: {message}")


def _object(
    value: Any,
    location: str,
    required: Iterable[str],
    errors: list[str],
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        _fail(errors, location, "must be an object")
        return None
    expected = set(required)
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing:
        _fail(errors, location, f"missing keys: {', '.join(missing)}")
    if unknown:
        _fail(errors, location, f"unknown keys: {', '.join(unknown)}")
    return value


def _string(
    value: Any,
    location: str,
    errors: list[str],
    *,
    choices: Iterable[str] | None = None,
) -> str | None:
    if not isinstance(value, str) or not value:
        _fail(errors, location, "must be a non-empty string")
        return None
    if choices is not None and value not in choices:
        _fail(errors, location, f"must be one of: {', '.join(choices)}")
    return value


def _identifier(value: Any, location: str, errors: list[str]) -> str | None:
    result = _string(value, location, errors)
    if result is not None and ID_PATTERN.fullmatch(result) is None:
        _fail(errors, location, "must use lowercase letters, numbers, '.', '_', or '-'")
    return result


def _integer(
    value: Any,
    location: str,
    errors: list[str],
    minimum: int,
    maximum: int,
) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(errors, location, "must be an integer")
        return None
    if not minimum <= value <= maximum:
        _fail(errors, location, f"must be between {minimum} and {maximum}")
    return value


def _string_list(
    value: Any,
    location: str,
    errors: list[str],
    *,
    choices: Iterable[str] | None = None,
    identifiers: bool = False,
    allow_empty: bool = True,
) -> list[str] | None:
    if not isinstance(value, list):
        _fail(errors, location, "must be an array")
        return None
    if not allow_empty and not value:
        _fail(errors, location, "must not be empty")
    parsed: list[str] = []
    for index, item in enumerate(value):
        item_location = f"{location}[{index}]"
        parsed_item = (
            _identifier(item, item_location, errors)
            if identifiers
            else _string(item, item_location, errors, choices=choices)
        )
        if parsed_item is not None:
            parsed.append(parsed_item)
    if len(set(parsed)) != len(parsed):
        _fail(errors, location, "must not contain duplicates")
    return parsed


def _command(value: Any, location: str, errors: list[str]) -> list[str] | None:
    command = _string_list(value, location, errors, allow_empty=False)
    if command is None:
        return None
    forbidden = {"|", "||", "&&", ";", ">", ">>", "<"}
    if any(token in forbidden for token in command):
        _fail(errors, location, "must be an argv array, not a shell command")
    allowed_placeholders = {"{python}", "{repo}"}
    for index, token in enumerate(command):
        placeholders = set(re.findall(r"\{[^{}]+\}", token))
        unknown = placeholders - allowed_placeholders
        if unknown:
            _fail(
                errors,
                f"{location}[{index}]",
                f"unknown placeholders: {', '.join(sorted(unknown))}",
            )
    if command and command[0] != "{python}":
        _fail(errors, location, "must use the current Python through {python}")
    if len(command) > 1 and (
        command[1].startswith("/") or ".." in Path(command[1]).parts
    ):
        _fail(errors, f"{location}[1]", "must name a repository-relative script")
    return command


def validate_feature_manifest(document: Any, path: Path) -> dict[str, Any]:
    errors: list[str] = []
    root = _object(
        document,
        str(path),
        (
            "schemaVersion",
            "proofLevels",
            "roles",
            "traceGroups",
            "checks",
            "capabilities",
        ),
        errors,
    )
    if root is None:
        raise ValidationFailure("\n".join(errors))
    if root.get("schemaVersion") != 1:
        _fail(errors, f"{path}.schemaVersion", "must equal 1")
    if root.get("proofLevels") != list(PROOF_LEVELS):
        _fail(errors, f"{path}.proofLevels", "must list S0 through S5 in order")
    if root.get("roles") != list(ROLES):
        _fail(errors, f"{path}.roles", "must match the canonical actor roles")
    if root.get("traceGroups") != list(TRACE_GROUPS):
        _fail(errors, f"{path}.traceGroups", "must match the canonical trace groups")

    checks = root.get("checks")
    check_ids: set[str] = set()
    if not isinstance(checks, list) or not checks:
        _fail(errors, f"{path}.checks", "must be a non-empty array")
        checks = []
    for index, item in enumerate(checks):
        location = f"{path}.checks[{index}]"
        check = _object(
            item,
            location,
            (
                "id",
                "title",
                "proofLevel",
                "costTier",
                "command",
                "requires",
                "sourcePatterns",
            ),
            errors,
        )
        if check is None:
            continue
        check_id = _identifier(check.get("id"), f"{location}.id", errors)
        if check_id in check_ids:
            _fail(errors, f"{location}.id", "duplicates another check")
        elif check_id is not None:
            check_ids.add(check_id)
        _string(check.get("title"), f"{location}.title", errors)
        _string(
            check.get("proofLevel"),
            f"{location}.proofLevel",
            errors,
            choices=PROOF_LEVELS,
        )
        _integer(check.get("costTier"), f"{location}.costTier", errors, 0, 5)
        _command(check.get("command"), f"{location}.command", errors)
        _string_list(
            check.get("requires"),
            f"{location}.requires",
            errors,
            choices=REQUIREMENTS,
        )
        patterns = _string_list(
            check.get("sourcePatterns"),
            f"{location}.sourcePatterns",
            errors,
            allow_empty=False,
        )
        if patterns is not None:
            for pattern in patterns:
                try:
                    fnmatch.translate(pattern)
                except re.error:
                    _fail(errors, f"{location}.sourcePatterns", f"invalid pattern: {pattern}")

    capabilities = root.get("capabilities")
    capability_ids: set[str] = set()
    scenario_references: set[str] = set()
    if not isinstance(capabilities, list) or not capabilities:
        _fail(errors, f"{path}.capabilities", "must be a non-empty array")
        capabilities = []
    for index, item in enumerate(capabilities):
        location = f"{path}.capabilities[{index}]"
        capability = _object(
            item,
            location,
            (
                "id",
                "title",
                "owner",
                "roles",
                "sourcePatterns",
                "checks",
                "scenarios",
                "docs",
                "traceGroups",
                "minimumProof",
            ),
            errors,
        )
        if capability is None:
            continue
        capability_id = _identifier(
            capability.get("id"), f"{location}.id", errors
        )
        if capability_id in capability_ids:
            _fail(errors, f"{location}.id", "duplicates another capability")
        elif capability_id is not None:
            capability_ids.add(capability_id)
        _string(capability.get("title"), f"{location}.title", errors)
        _string(capability.get("owner"), f"{location}.owner", errors)
        _string_list(
            capability.get("roles"),
            f"{location}.roles",
            errors,
            choices=ROLES,
            allow_empty=False,
        )
        _string_list(
            capability.get("sourcePatterns"),
            f"{location}.sourcePatterns",
            errors,
            allow_empty=False,
        )
        capability_checks = _string_list(
            capability.get("checks"),
            f"{location}.checks",
            errors,
            identifiers=True,
        )
        if capability_checks is not None:
            for check_id in capability_checks:
                if check_id not in check_ids:
                    _fail(errors, f"{location}.checks", f"unknown check: {check_id}")
        scenarios = _string_list(
            capability.get("scenarios"),
            f"{location}.scenarios",
            errors,
            identifiers=True,
        )
        if scenarios is not None:
            scenario_references.update(scenarios)
        _string_list(
            capability.get("docs"),
            f"{location}.docs",
            errors,
            allow_empty=False,
        )
        _string_list(
            capability.get("traceGroups"),
            f"{location}.traceGroups",
            errors,
            choices=TRACE_GROUPS,
        )
        _string_list(
            capability.get("minimumProof"),
            f"{location}.minimumProof",
            errors,
            choices=PROOF_LEVELS,
            allow_empty=False,
        )

    if errors:
        raise ValidationFailure("\n".join(errors))
    root["_checkIds"] = check_ids
    root["_capabilityIds"] = capability_ids
    root["_scenarioReferences"] = scenario_references
    return root


def validate_scenario(document: Any, path: Path) -> dict[str, Any]:
    errors: list[str] = []
    root = _object(
        document,
        str(path),
        (
            "schemaVersion",
            "id",
            "title",
            "status",
            "capabilities",
            "proofLevel",
            "costTier",
            "fixture",
            "events",
            "stop",
            "expect",
            "capture",
            "adapter",
        ),
        errors,
    )
    if root is None:
        raise ValidationFailure("\n".join(errors))
    if root.get("schemaVersion") != 1:
        _fail(errors, f"{path}.schemaVersion", "must equal 1")
    scenario_id = _identifier(root.get("id"), f"{path}.id", errors)
    if scenario_id is not None and path.stem != scenario_id:
        _fail(errors, f"{path}.id", "must equal the file name without .json")
    _string(root.get("title"), f"{path}.title", errors)
    status = _string(
        root.get("status"), f"{path}.status", errors, choices=SCENARIO_STATUSES
    )
    _string_list(
        root.get("capabilities"),
        f"{path}.capabilities",
        errors,
        identifiers=True,
        allow_empty=False,
    )
    _string(
        root.get("proofLevel"),
        f"{path}.proofLevel",
        errors,
        choices=PROOF_LEVELS,
    )
    _integer(root.get("costTier"), f"{path}.costTier", errors, 0, 5)

    fixture = _object(
        root.get("fixture"),
        f"{path}.fixture",
        ("rom", "save", "seed"),
        errors,
    )
    if fixture is not None:
        if fixture.get("rom") is not None:
            _string(fixture.get("rom"), f"{path}.fixture.rom", errors)
        save = fixture.get("save")
        if save is not None:
            save_object = _object(
                save, f"{path}.fixture.save", ("path", "kind"), errors
            )
            if save_object is not None:
                _string(save_object.get("path"), f"{path}.fixture.save.path", errors)
                _string(
                    save_object.get("kind"),
                    f"{path}.fixture.save.kind",
                    errors,
                    choices=("dsv", "sav"),
                )
        _integer(fixture.get("seed"), f"{path}.fixture.seed", errors, 0, 0xFFFFFFFF)

    events = root.get("events")
    if not isinstance(events, list):
        _fail(errors, f"{path}.events", "must be an array")
        events = []
    previous_at = -1
    for index, item in enumerate(events):
        location = f"{path}.events[{index}]"
        event = _object(item, location, ("at", "kind", "value"), errors)
        if event is None:
            continue
        at = _integer(event.get("at"), f"{location}.at", errors, 0, 0x7FFFFFFF)
        if at is not None and at < previous_at:
            _fail(errors, f"{location}.at", "events must be ordered")
        elif at is not None:
            previous_at = at
        _string(event.get("kind"), f"{location}.kind", errors, choices=EVENT_KINDS)
        _string(event.get("value"), f"{location}.value", errors)

    stop = _object(
        root.get("stop"), f"{path}.stop", ("frameBudget", "condition"), errors
    )
    if stop is not None:
        _integer(stop.get("frameBudget"), f"{path}.stop.frameBudget", errors, 1, 1000000)
        _string(stop.get("condition"), f"{path}.stop.condition", errors)

    expect = _object(
        root.get("expect"),
        f"{path}.expect",
        ("requiredEvents", "forbiddenEvents", "invariants"),
        errors,
    )
    if expect is not None:
        _string_list(
            expect.get("requiredEvents"),
            f"{path}.expect.requiredEvents",
            errors,
            choices=SEMANTIC_EVENTS,
        )
        _string_list(
            expect.get("forbiddenEvents"),
            f"{path}.expect.forbiddenEvents",
            errors,
            choices=SEMANTIC_EVENTS,
        )
        _string_list(
            expect.get("invariants"),
            f"{path}.expect.invariants",
            errors,
            allow_empty=False,
        )
    _string(root.get("capture"), f"{path}.capture", errors, choices=CAPTURE_POLICIES)

    adapter = root.get("adapter")
    if adapter is None:
        if status == "active":
            _fail(errors, f"{path}.adapter", "active scenarios need an adapter")
    else:
        if status == "planned":
            _fail(errors, f"{path}.adapter", "planned scenarios must not claim a live adapter")
        adapter_kind_value = adapter.get("kind") if isinstance(adapter, dict) else None
        adapter_keys = (
            ("kind", "checks")
            if adapter_kind_value == "actor-observation"
            else ("kind", "commands", "result")
        )
        adapter_object = _object(
            adapter,
            f"{path}.adapter",
            adapter_keys,
            errors,
        )
        if adapter_object is not None:
            adapter_kind = _string(
                adapter_object.get("kind"),
                f"{path}.adapter.kind",
                errors,
                choices=("command-sequence", "actor-observation"),
            )
            if adapter_kind == "command-sequence" and expect is not None:
                if expect.get("requiredEvents") or expect.get("forbiddenEvents"):
                    _fail(
                        errors,
                        f"{path}.expect",
                        "command-sequence adapters do not inspect semantic events",
                    )
            if adapter_kind == "command-sequence":
                commands = adapter_object.get("commands")
                if not isinstance(commands, list) or not commands:
                    _fail(errors, f"{path}.adapter.commands", "must be a non-empty array")
                else:
                    for index, command in enumerate(commands):
                        _command(command, f"{path}.adapter.commands[{index}]", errors)
                _string(
                    adapter_object.get("result"),
                    f"{path}.adapter.result",
                    errors,
                    choices=RESULT_KINDS,
                )
            elif adapter_kind == "actor-observation":
                if fixture is not None and fixture.get("rom") is None:
                    _fail(
                        errors,
                        f"{path}.fixture.rom",
                        "actor observation needs an explicit ROM fixture",
                    )
                checks = _string_list(
                    adapter_object.get("checks"),
                    f"{path}.adapter.checks",
                    errors,
                    choices=ACTOR_SEMANTIC_CHECKS,
                    allow_empty=False,
                )
                if checks is not None and "trace-window-complete" not in checks:
                    _fail(
                        errors,
                        f"{path}.adapter.checks",
                        "actor observation requires trace-window-complete",
                    )
                if expect is not None and checks is not None:
                    invariants = expect.get("invariants")
                    if isinstance(invariants, list):
                        for index, invariant in enumerate(invariants):
                            registered = ACTOR_INVARIANT_CHECKS.get(invariant)
                            location = f"{path}.expect.invariants[{index}]"
                            if registered is None:
                                _fail(
                                    errors,
                                    location,
                                    "actor observation needs an exact registered invariant",
                                )
                                continue
                            missing_checks = [
                                check for check in registered if check not in checks
                            ]
                            if missing_checks:
                                _fail(
                                    errors,
                                    location,
                                    "needs adapter checks: "
                                    + ", ".join(missing_checks),
                                )

    if errors:
        raise ValidationFailure("\n".join(errors))
    return root


def load_feature_manifest(path: Path) -> dict[str, Any]:
    return validate_feature_manifest(load_json_document(path), path)


def load_scenarios(directory: Path) -> dict[str, dict[str, Any]]:
    if not directory.is_dir():
        raise ValidationFailure(f"missing scenario directory: {directory}")
    paths = sorted(directory.glob("*.json"))
    if not paths:
        raise ValidationFailure(f"no scenarios found under: {directory}")
    scenarios: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for path in paths:
        try:
            scenario = validate_scenario(load_json_document(path), path)
        except ValidationFailure as error:
            errors.append(str(error))
            continue
        scenario_id = scenario["id"]
        if scenario_id in scenarios:
            errors.append(f"{path}: duplicate scenario ID: {scenario_id}")
        scenarios[scenario_id] = scenario
    if errors:
        raise ValidationFailure("\n".join(errors))
    return scenarios


def cross_validate(
    manifest: dict[str, Any],
    scenarios: dict[str, dict[str, Any]],
    repo: Path | None = None,
) -> None:
    errors: list[str] = []
    capability_ids = manifest["_capabilityIds"]
    manifest_scenarios = manifest["_scenarioReferences"]
    scenario_capabilities = {
        scenario_id: set(scenario["capabilities"])
        for scenario_id, scenario in scenarios.items()
    }
    capability_scenarios = {
        capability["id"]: set(capability["scenarios"])
        for capability in manifest["capabilities"]
    }
    for scenario_id, scenario in scenarios.items():
        for capability_id in scenario["capabilities"]:
            if capability_id not in capability_ids:
                errors.append(
                    f"scenario {scenario_id}: unknown capability: {capability_id}"
                )
            elif scenario_id not in capability_scenarios[capability_id]:
                errors.append(
                    f"scenario {scenario_id}: capability {capability_id} does not link back"
                )
    for capability_id, linked_scenarios in capability_scenarios.items():
        for scenario_id in linked_scenarios:
            if (
                scenario_id in scenario_capabilities
                and capability_id not in scenario_capabilities[scenario_id]
            ):
                errors.append(
                    f"capability {capability_id}: scenario {scenario_id} does not link back"
                )
    missing_files = sorted(manifest_scenarios - set(scenarios))
    unreferenced = sorted(set(scenarios) - manifest_scenarios)
    if missing_files:
        errors.append("manifest scenarios without files: " + ", ".join(missing_files))
    if unreferenced:
        errors.append("scenario files missing from manifest: " + ", ".join(unreferenced))
    if repo is not None:
        behavior_schema_path = repo / "tools/overworld/behavior_schema.json"
        behavior_schema = load_json_document(behavior_schema_path)
        schema_feature_ids = behavior_schema.get("featureIds") \
            if isinstance(behavior_schema, dict) else None
        if not isinstance(schema_feature_ids, list) or not all(
            isinstance(item, str) for item in schema_feature_ids
        ):
            errors.append(
                "behavior schema featureIds must be an array of strings"
            )
        else:
            missing_capabilities = sorted(
                set(schema_feature_ids) - capability_ids
            )
            if missing_capabilities:
                errors.append(
                    "behavior schema feature IDs without capabilities: "
                    + ", ".join(missing_capabilities)
                )
        for check in manifest["checks"]:
            script = Path(check["command"][1])
            if script.is_absolute() or ".." in script.parts:
                errors.append(f"check {check['id']}: command script escapes the repository")
            elif not (repo / script).is_file():
                errors.append(f"check {check['id']}: command script is missing: {script}")
        for capability in manifest["capabilities"]:
            for document in capability["docs"]:
                path = Path(document)
                if path.is_absolute() or ".." in path.parts:
                    errors.append(
                        f"capability {capability['id']}: document escapes the repository"
                    )
                elif not (repo / path).is_file():
                    errors.append(
                        f"capability {capability['id']}: document is missing: {document}"
                    )
    if errors:
        raise ValidationFailure("\n".join(errors))
