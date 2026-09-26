"""Strict validators for overworld host-control data."""

from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import re
import sys
from datetime import date
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
VERIFICATION_KINDS = ("normal-play", "controlled-case", "observer-control")
SETUP_MUTATION_TARGETS = (
    "fixture", "profile", "position", "actors", "counters", "rng",
    "control-result", "observation",
)
CAPTURE_POLICIES = ("none", "failure", "always")
EVENT_KINDS = ("input", "lifecycle", "setup")
RESULT_KINDS = ("exit-zero", "json-passed")
RUNTIME_PROOF_CLAIMS = (
    "battle-capture-handoff",
    "collision-decision",
    "controlled-action",
    "control-release",
    "engine-boundary",
    "feedback-effect",
    "frame-pacing",
    "host-cpu-pacing",
    "live-actor-identity",
    "logical-commit",
    "natural-input",
    "population-bounds",
    "profile-resolution",
    "rendered-motion",
    "streaming-path",
    "terrain-selection",
    "world-transition",
)
ACTOR_SEMANTIC_CHECKS = (
    "trace-window-complete",
    "terminal-result",
    "no-commit-after-cancel",
    "control-returned",
    "single-motion-owner",
    "target-reservation-serialized",
    "path-advances-before-commit",
    "field-epoch-current",
    "presentation-attached",
    "mounted-presentation-coordinates-equal",
    "mounted-presentation-facing-locked",
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
    "A target reservation rejects another actor until the owner releases it": (
        "target-reservation-serialized",
    ),
    "Every path advance is ordered before the terminal logical commit": (
        "path-advances-before-commit",
    ),
    "Every active actor handle uses the current field epoch": (
        "field-epoch-current",
    ),
    "Every active actor has an attached presentation": (
        "presentation-attached",
    ),
    "Mounted player and follower coordinates match for every published motion sample": (
        "mounted-presentation-coordinates-equal",
    ),
    "Mounted player and follower facing remains locked for every published skid sample": (
        "mounted-presentation-facing-locked",
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
    "MOUNT_PRESENTATION_POSITION",
    "MOUNT_PRESENTATION_STATE",
)
SEMANTIC_REASONS = (
    "OK",
    "RETRY_WORLD_BUSY",
    "REJECTED_BLOCKED",
    "REJECTED_SIDE_TILE",
    "REJECTED_TERRAIN",
    "REJECTED_OCCUPIED",
    "REJECTED_RESERVED",
    "REJECTED_DIRECTION",
    "REJECTED_PROFILE",
    "UNSUPPORTED_LOCOMOTION",
    "MOTION_ALREADY_ACTIVE",
    "STALE_ACTOR",
    "STALE_FIELD",
    "PRESENTATION_MISSING",
    "DATA_UNAVAILABLE",
    "NO_MEMORY",
    "CONTEXT_LOST",
    "INVALID_ARGUMENT",
    "QUEUE_FULL",
    "UNSUPPORTED_COMMAND",
    "STALE_SEQUENCE",
)


class ValidationFailure(ValueError):
    """Raised when a strict control document is invalid."""


PRIVATE_PROOF_STATE_NAMES = {
    "MOUNT",
    "MOUNT_PROFILE",
    "MOUNT_POLICY_FIELDS",
    "MOUNT_POLICY_LAYOUT",
}
PRIVATE_PROOF_STATE_PREFIXES = (
    "MOUNT_PROFILE_",
    "MOUNT_POLICY_",
)
PRIVATE_PROOF_STATE_CALLS = {
    "actor_motion_receipt_state",
    "mount_boundary_settled",
    "mount_state",
    "movement_policy_state",
    "reset_public_walk_policy",
    "resolve_movement_policy_state",
}
DIRECT_PROOF_STATE_WRITES = {
    "write_bytes",
    "write_u8",
    "write_u16",
    "write_u32",
}
PUBLIC_PROOF_TRANSPORT_FUNCTIONS = {
    "actor_memory_read",
    "actor_memory_write",
    "actor_state",
    "actor_trace_begin",
    "actor_trace_capture",
    "actor_trace_finish",
    "read_actor_memory",
}
RAW_ACTOR_MEMORY_PORTS = {
    "actor_memory_read",
    "actor_memory_write",
    "read_actor_memory",
}
PACKAGED_SERVICE_TRANSPORT_FUNCTIONS = {
    "launch_packaged_resolver_transport",
    "restore_packaged_resolver_transport",
}
FORBIDDEN_PROOF_LANGUAGE_CALLS = {
    "__getattribute__",
    "eval",
    "exec",
    "getattr",
}
PROCESS_LAUNCH_CALLS = {
    "Popen",
    "call",
    "check_call",
    "check_output",
    "run",
}

# These are collector implementation modules, not trusted transports. Every
# reached helper/class is audited with the same rules as the registered runner.
LOCAL_PROOF_MODULES = {
    "tools.overworld.runtime_actor_binding": "tools/overworld/runtime_actor_binding.py",
    "tools.overworld.runtime_normal_play": "tools/overworld/runtime_normal_play.py",
    "tools.overworld.runtime_normal_healing": "tools/overworld/runtime_normal_healing.py",
    "tools.overworld.normal_play_observer": "tools/overworld/normal_play_observer.py",
    "tools.overworld.spawn_identity": "tools/overworld/spawn_identity.py",
    "tools.overworld.runtime_cadence": "tools/overworld/runtime_cadence.py",
}
EXISTING_PROOF_IMPORT_BOUNDARIES = {
    "tools.overworld.actor_probe", "tools.overworld.trace",
}


def _function_ast_shape(source: str) -> str:
    return ast.dump(ast.parse(source).body[0], include_attributes=False)


PUBLIC_PROOF_TRANSPORT_SHAPES = {
    "actor_memory_read": _function_ast_shape("""
def actor_memory_read(emu, address, size):
    return bytes(emu.memory.unsigned[address:address + size:1])
"""),
    "actor_memory_write": _function_ast_shape("""
def actor_memory_write(emu, address, data):
    emu.memory.unsigned[address:address + len(data):1] = list(data)
"""),
    "actor_state": _function_ast_shape("""
def actor_state(emu, slot):
    state = ACTOR_DESCRIPTOR["state"]
    address = (
        state["address"]
        + state["offsets"]["actors"]
        + slot * state["actorStride"]
    )
    return actor_probe.decode_actor_state(
        actor_memory_read(emu, address, ACTOR_STATE_SIZE),
        ACTOR_DESCRIPTOR,
    )
"""),
    "actor_trace_begin": _function_ast_shape('''
def actor_trace_begin(emu, event_names, frame_budget, slot=None):
    """Arm public Actor trace storage without exposing its raw address port."""
    if ACTOR_EVIDENCE_OUTPUT is None:
        return None
    schema = load_trace_schema(
        REPO / "tools/overworld/schemas/semantic-trace-v1.json"
    )
    event_ids = {
        name: int(value)
        for value, name in schema["events"].items()
    }
    event_mask = sum(1 << event_ids[name] for name in event_names)
    actor = None if slot is None else actor_state(emu, slot)
    actor_probe.configure_runtime_trace(
        lambda address, size: actor_memory_read(emu, address, size),
        lambda address, data: actor_memory_write(emu, address, data),
        ACTOR_DESCRIPTOR,
        event_mask=event_mask,
        frame_budget=frame_budget,
        actor=None if actor is None else actor["handle"],
    )
    return schema
'''),
    "actor_trace_capture": _function_ast_shape('''
def actor_trace_capture(emu, schema):
    """Capture public Actor state and trace through the typed probe boundary."""
    if schema is None:
        return None
    read_memory = lambda address, size: actor_memory_read(
        emu, address, size
    )
    return actor_probe.capture_observation(
        read_memory,
        ACTOR_DESCRIPTOR,
        schema,
    )
'''),
    "actor_trace_finish": _function_ast_shape('''
def actor_trace_finish(emu, schema):
    """Close and capture public Actor trace through the typed probe boundary."""
    if schema is None:
        return None
    read_memory = lambda address, size: actor_memory_read(
        emu, address, size
    )
    actor_probe.finish_runtime_trace(
        read_memory,
        lambda address, data: actor_memory_write(emu, address, data),
        ACTOR_DESCRIPTOR,
    )
    return actor_probe.capture_observation(
        read_memory,
        ACTOR_DESCRIPTOR,
        schema,
    )
'''),
}

STARTUP_IDENTITY_TRANSPORT_SHAPES = {
    "linked_symbols": _function_ast_shape('''
def linked_symbols(path):
    output = subprocess.run(
        [NM, "-n", str(path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    symbols = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            try:
                symbols[parts[2]] = int(parts[0], 16)
            except ValueError:
                pass
    return symbols
'''),
}

# Narrow public service buffers used by the read-only entry/return recorder.
# Matching a reader alone is insufficient: audit() also checks its hook,
# register-derived pointer and call site. No arbitrary raw address port is
# exported to normal proof code.
ABI_PROOF_TRANSPORT_MODULE = "tools.overworld.runtime_normal_play"
ABI_PROOF_TRANSPORT_SHAPES = {
    "_public_abi_address": _function_ast_shape('''
def _public_abi_address(address, size, *, allow_stack=False):
    main_ram = 0x02000000 <= address < address + size <= 0x02400000
    dtcm = allow_stack and 0x027E0000 <= address < address + size <= 0x027E3FC0
    if address & 3 or not (main_ram or dtcm):
        raise ObservationFailure(
            f"public ABI buffer address={address:#010x}, size={size} "
            "is unaligned or outside main RAM/DTCM public-buffer bounds")
    return address
'''),
    "read_resolver_request": _function_ast_shape('''
def read_resolver_request(rt, emu, address):
    """BehaviorResolveRequest: fixed 44-byte conditional-profile input at r2."""
    value = rt.actor_memory_read(emu, _public_abi_address(address, 44, allow_stack=True), 44)
    if len(value) != 44:
        raise ObservationFailure("public resolver request byte count changed")
    return value
'''),
    "read_resolver_result": _function_ast_shape('''
def read_resolver_result(rt, emu, address):
    """BehaviorResolveResult v2: fixed 200-byte conditional-profile output."""
    value = rt.actor_memory_read(emu, _public_abi_address(address, 200, allow_stack=True), 200)
    if len(value) != 200:
        raise ObservationFailure("public resolver result byte count changed")
    return value
'''),
    "read_walk_policy_call": _function_ast_shape('''
def read_walk_policy_call(rt, emu, address):
    """OverworldActorWalkPolicyCall v1: fixed public request/reply at r0."""
    value = rt.actor_memory_read(emu, _public_abi_address(address, 28, allow_stack=True), 28)
    if len(value) != 28 or value[:4] != b"\\x01\\x00\\x1c\\x00":
        raise ObservationFailure("public Walk policy call ABI changed")
    return value
'''),
    "read_resolved_lane": _function_ast_shape('''
def read_resolved_lane(rt, emu, address, schema):
    """One current 72-byte lane addressed by the checked public Walk policy call."""
    if schema["compactSize"] != 72:
        raise ObservationFailure("normal recorder supports only current public lanes")
    value = rt.actor_memory_read(emu, _public_abi_address(address, 72, allow_stack=True), 72)
    if len(value) != 72:
        raise ObservationFailure("public resolved lane byte count changed")
    return value
'''),
}
ABI_PROOF_CALL_SITES = {
    ("resolver_before", "read_resolver_request"): "read_resolver_request(rt, emu, regs.r2)",
    ("resolver_after", "read_resolver_result"): 'read_resolver_result(rt, emu, context["resultAddress"])',
    ("policy_before", "read_walk_policy_call"): "read_walk_policy_call(rt, emu, address)",
    ("policy_after", "read_walk_policy_call"): 'read_walk_policy_call(rt, emu, context["address"])',
    ("policy_before", "read_resolved_lane"): 'read_resolved_lane(rt, emu, int.from_bytes(call[4:8], "little"), self.schema)',
}


def _runtime_call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _is_emulator_memory_store(node: ast.Subscript) -> bool:
    return _is_emulator_memory_value(node.value)


def _is_emulator_memory_value(value: ast.AST) -> bool:
    attributes = {
        child.attr
        for child in ast.walk(value)
        if isinstance(child, ast.Attribute)
    }
    return "memory" in attributes and bool(
        {"unsigned", "signed"} & attributes
    )


def _root_name(node: ast.AST) -> str | None:
    while isinstance(node, (ast.Attribute, ast.Subscript)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


class _DirectFunctionNodes(ast.NodeVisitor):
    """Collect one function body without merging nested callback bodies."""

    def __init__(self) -> None:
        self.nodes: list[ast.AST] = []
        self.parents: dict[ast.AST, ast.AST] = {}
        self.nested: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        self._parent: ast.AST | None = None

    def visit(self, node: ast.AST) -> Any:
        previous = self._parent
        if previous is not None:
            self.parents[node] = previous
        self.nodes.append(node)
        self._parent = node
        try:
            return super().visit(node)
        finally:
            self._parent = previous

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.nested.append(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.nested.append(node)


def _direct_function_nodes(
    function: ast.FunctionDef | ast.AsyncFunctionDef,
) -> _DirectFunctionNodes:
    collector = _DirectFunctionNodes()
    for expression in (
        *function.decorator_list, *function.args.defaults,
        *(value for value in function.args.kw_defaults if value is not None),
    ):
        collector.visit(expression)
    for statement in function.body:
        collector.visit(statement)
    return collector


def _runtime_scenario_functions(tree: ast.Module) -> dict[str, str]:
    scenarios: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not any(
            isinstance(target, ast.Name) and target.id == "SCENARIOS"
            for target in node.targets
        ) or not isinstance(node.value, ast.Dict):
            continue
        for key, value in zip(node.value.keys, node.value.values):
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and isinstance(value, ast.Name)
            ):
                scenarios[key.value] = value.id
    return scenarios


def scenario_uses_public_actor_evidence(scenario: dict[str, Any]) -> bool:
    adapter = scenario.get("adapter")
    subjects = scenario.get("subjects")
    if not isinstance(adapter, dict) or adapter.get("kind") != "actor-observation":
        return False
    claims = adapter.get("claims")
    checks = adapter.get("checks")
    if (
        not isinstance(claims, list)
        or "live-actor-identity" not in claims
        or not isinstance(checks, list)
        or not {"trace-window-complete", "terminal-result"}.issubset(checks)
        or not isinstance(subjects, list)
        or not subjects
    ):
        return False
    return any(
        isinstance(subject, dict)
        and subject.get("motionActor") is True
        and subject.get("requirePresentation") is True
        for subject in subjects
    )


class RuntimeProofSourceAudit:
    """Fail-closed source audit for registered executable ROM proof paths."""

    def __init__(
        self, source: str, *, repo: Path | None = None,
        local_module_sources: dict[str, str] | None = None,
        _root: RuntimeProofSourceAudit | None = None,
        _module_name: str = "runner",
    ) -> None:
        self.root_audit = _root or self
        self.module_name = _module_name
        if _root is None:
            self.repo = repo
            self.local_module_sources = local_module_sources or {}
            self.module_audits: dict[str, RuntimeProofSourceAudit] = {}
            self.function_owners: dict[int, RuntimeProofSourceAudit] = {}
            self.runtime_value_functions: dict[str, ast.FunctionDef] = {}
            self.runtime_name_cache: dict[int, set[str]] = {}
            self.routing_errors: set[str] = set()
        self.error: str | None = None
        try:
            self.tree = ast.parse(source)
        except SyntaxError as error:
            self.tree = ast.Module(body=[], type_ignores=[])
            self.error = f"cannot parse runner source: {error}"
        self.functions = {
            node.name: node
            for node in self.tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.classes = {
            node.name: node for node in self.tree.body
            if isinstance(node, ast.ClassDef)
        }
        self.imports: dict[str, tuple[str, str | None]] = {}
        self.import_errors: set[str] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    module, member = node.module, alias.name
                    if node.level:
                        package = self.module_name.split(".")[:-node.level]
                        module = ".".join([*package, module])
                    if module == "tools.overworld":
                        module, member = f"{module}.{alias.name}", None
                    if module.startswith("tools."):
                        self.imports[alias.asname or alias.name] = (module, member)
                    elif self.module_name != "runner" and module.split(".")[0] not in sys.stdlib_module_names:
                        self.import_errors.add(f"unregistered local proof import: {module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("tools."):
                        self.imports[alias.asname or alias.name] = (alias.name, None)
                    elif self.module_name != "runner" and alias.name.split(".")[0] not in sys.stdlib_module_names:
                        self.import_errors.add(f"unregistered local proof import: {alias.name}")
        for node in ast.walk(self.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.root_audit.function_owners[id(node)] = self
        # Imports execute module/class initializers even if their assigned
        # values are never used. Keep those reads/writes in the proof closure.
        self.initializer = ast.FunctionDef(
            name="import_initializers", args=ast.arguments(
                posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
            body=[node for node in self.tree.body if not isinstance(node, (
                ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                ast.Import, ast.ImportFrom,
            ))], decorator_list=[], lineno=1, col_offset=0,
        )
        for definition in self.classes.values():
            self.initializer.body.extend(node for node in definition.body
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
        for name in self.imports:
            self.initializer.body.append(ast.Expr(value=ast.Name(
                id=name, ctx=ast.Load(), lineno=1, col_offset=0)))
        self.root_audit.function_owners[id(self.initializer)] = self
        parents: dict[ast.AST, ast.AST] = {}
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        self.function_parents: dict[int, ast.FunctionDef | ast.AsyncFunctionDef] = {}
        self.nested_functions: dict[
            int,
            dict[str, list[ast.FunctionDef | ast.AsyncFunctionDef]],
        ] = {}
        for node in ast.walk(self.tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            parent = parents.get(node)
            while parent is not None and not isinstance(
                parent, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                parent = parents.get(parent)
            if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.function_parents[id(node)] = parent
                self.nested_functions.setdefault(id(parent), {}).setdefault(
                    node.name, []
                ).append(node)
        self.module_values: dict[str, ast.AST] = {}
        for node in self.tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self.module_values[target.id] = node.value
            elif (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and node.value is not None
            ):
                self.module_values[node.target.id] = node.value
        self.scenarios = _runtime_scenario_functions(self.tree)
        self.trusted_public_transports = {
            name
            for name, expected in PUBLIC_PROOF_TRANSPORT_SHAPES.items()
            if name in self.functions
            and ast.dump(
                self.functions[name], include_attributes=False
            ) == expected
        }
        self.trusted_startup_transports = {
            name
            for name, expected in STARTUP_IDENTITY_TRANSPORT_SHAPES.items()
            if name in self.functions
            and ast.dump(
                self.functions[name], include_attributes=False
            ) == expected
        }
        guard = self.functions.get("_public_abi_address")
        valid_abi_guard = self.module_name == ABI_PROOF_TRANSPORT_MODULE \
            and guard is not None and ast.dump(guard, include_attributes=False) \
                == ABI_PROOF_TRANSPORT_SHAPES["_public_abi_address"]
        self.trusted_abi_transports = {
            name for name, expected in ABI_PROOF_TRANSPORT_SHAPES.items()
            if valid_abi_guard and name in self.functions
            and ast.dump(self.functions[name], include_attributes=False) == expected
        }

    def _lexical_functions(
        self,
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        name: str,
    ) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
        owner = self.root_audit.function_owners.get(id(function), self)
        matches: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
        scope: ast.FunctionDef | ast.AsyncFunctionDef | None = function
        while scope is not None:
            matches.extend(
                owner.nested_functions.get(id(scope), {}).get(name, ())
            )
            scope = owner.function_parents.get(id(scope))
        helper = owner.functions.get(name)
        if helper is not None:
            matches.append(helper)
        definition = owner.classes.get(name)
        if definition is not None:
            matches.extend(node for node in ast.walk(definition)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))
        if name in owner.imports:
            module, member = owner.imports[name]
            matches.extend(self._imported_functions(module, member, owner))
        return matches

    def _imported_functions(
        self, module: str, member: str | None,
        caller: RuntimeProofSourceAudit | None = None,
    ) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
        root = self.root_audit
        if module in EXISTING_PROOF_IMPORT_BOUNDARIES:
            if caller is not None and caller is not root:
                root.routing_errors.add(
                    f"collector must use the typed runner boundary, not import {module}")
            return []
        if module not in LOCAL_PROOF_MODULES:
            root.routing_errors.add(f"unregistered local proof import: {module}")
            return []
        owner = root.module_audits.get(module)
        if owner is None:
            try:
                source = root.local_module_sources.get(module)
                if source is None:
                    if root.repo is None:
                        raise OSError("repository source root was not supplied")
                    path = root.repo / LOCAL_PROOF_MODULES[module]
                    if not path.resolve().is_relative_to(root.repo.resolve()):
                        raise OSError("local proof module escapes the repository")
                    source = path.read_text()
                owner = RuntimeProofSourceAudit(source, _root=root, _module_name=module)
                root.module_audits[module] = owner
            except (OSError, UnicodeError) as error:
                root.routing_errors.add(f"cannot read local proof module {module}: {error}")
                return []
        if owner.error:
            root.routing_errors.add(f"{module}: {owner.error}")
            return []
        root.routing_errors.update(owner.import_errors)
        if module == ABI_PROOF_TRANSPORT_MODULE and member in ABI_PROOF_TRANSPORT_SHAPES:
            root.routing_errors.add(f"public ABI reader cannot be imported directly: {member}")
        result = [owner.initializer]
        if member is None:
            return result
        if member in owner.functions:
            return result + [owner.functions[member]]
        if member in owner.classes:
            return result + [node for node in ast.walk(owner.classes[member])
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        if member in owner.module_values:
            return result  # The initializer includes the assigned value.
        root.routing_errors.add(f"local proof export is missing: {module}.{member}")
        return result

    def _attribute_functions(
        self, function: ast.FunctionDef | ast.AsyncFunctionDef,
        node: ast.Attribute,
    ) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
        owner = self.root_audit.function_owners.get(id(function), self)
        receiver = ast.unparse(node.value)
        if receiver in owner.imports:
            module, member = owner.imports[receiver]
            if member is None:
                return self._imported_functions(module, node.attr, owner)
        # Collector rt is the shared runner passed at its explicit entry. A
        # second arbitrary module facade is not part of this bounded route.
        runtime_names = self.root_audit.runtime_name_cache.get(id(function))
        if runtime_names is None:
            runtime_names = {"rt"}
            scope = function
            bindings = []
            while scope is not None:
                bindings.extend(_direct_function_nodes(scope).nodes)
                scope = owner.function_parents.get(id(scope))
            changed = True
            while changed:
                changed = False
                for binding in bindings:
                    if isinstance(binding, ast.Assign) and isinstance(binding.value, ast.Name) \
                            and binding.value.id in runtime_names:
                        for target in binding.targets:
                            if isinstance(target, ast.Name) and target.id not in runtime_names:
                                runtime_names.add(target.id)
                                changed = True
            self.root_audit.runtime_name_cache[id(function)] = runtime_names
        runtime = isinstance(node.value, ast.Name) and node.value.id in runtime_names
        runtime |= isinstance(node.value, ast.Attribute) and node.value.attr == "rt"
        if runtime:
            helper = self.root_audit.functions.get(node.attr)
            if helper is not None:
                return [helper]
            value = self.root_audit.module_values.get(node.attr)
            if value is not None:
                helper = self.root_audit.runtime_value_functions.get(node.attr)
                if helper is None:
                    helper = ast.FunctionDef(
                        name=f"runtime_value_{node.attr}", args=ast.arguments(
                            posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                        body=[ast.Expr(value=value)], decorator_list=[],
                        lineno=getattr(value, "lineno", 1), col_offset=0,
                    )
                    self.root_audit.runtime_value_functions[node.attr] = helper
                    self.root_audit.function_owners[id(helper)] = self.root_audit
                return [helper]
            else:
                self.root_audit.routing_errors.add(
                    f"shared runner attribute is missing: rt.{node.attr}")
        return []

    def _abi_call_is_typed(
        self, function: ast.FunctionDef | ast.AsyncFunctionDef, call: ast.Call,
    ) -> bool:
        owner = self.function_owners.get(id(function), self)
        name = _runtime_call_name(call)
        expression = ABI_PROOF_CALL_SITES.get((function.name, name))
        if expression is None or name not in owner.trusted_abi_transports:
            return False
        if ast.dump(call, include_attributes=False) != ast.dump(
            ast.parse(expression, mode="eval").body, include_attributes=False,
        ):
            return False
        install = owner.function_parents.get(id(function))
        if install is None or install.name != "install":
            return False
        actor_class = owner.classes.get("LedybaCollector")
        if actor_class is None or install not in actor_class.body:
            return False
        prefix = "resolver" if function.name.startswith("resolver_") else "policy"
        before = owner.nested_functions.get(id(install), {}).get(prefix + "_before", [])
        if len(before) != 1:
            return False
        before_nodes = _direct_function_nodes(before[0]).nodes
        bindings = {
            "regs": "emu.memory.register_arm9",
        } if prefix == "resolver" else {
            "address": "emu.memory.register_arm9.r0",
            "call": "read_walk_policy_call(rt, emu, address)",
        }
        for variable, expected in bindings.items():
            writes = [node for node in before_nodes
                if isinstance(node, ast.Name) and node.id == variable
                and isinstance(node.ctx, (ast.Store, ast.Del))]
            assignments = [node for node in before_nodes
                if isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == variable]
            if len(writes) != 1 or len(assignments) != 1 or ast.dump(
                assignments[0].value, include_attributes=False,
            ) != ast.dump(ast.parse(expected, mode="eval").body, include_attributes=False):
                return False
        pointer_key = "resultAddress" if prefix == "resolver" else "address"
        pointer_value = "regs.r3" if prefix == "resolver" else "address"
        pointers = [value for node in before_nodes if isinstance(node, ast.Dict)
            for key, value in zip(node.keys, node.values)
            if isinstance(key, ast.Constant) and key.value == pointer_key]
        if not pointers or any(ast.unparse(value) != pointer_value for value in pointers):
            return False
        if function.name.endswith("_after"):
            if [argument.arg for argument in function.args.args] != ["context"]:
                return False
            nodes = _direct_function_nodes(function).nodes
            if any(isinstance(node, (ast.Attribute, ast.Subscript, ast.Name))
                and isinstance(node.ctx, (ast.Store, ast.Del))
                and _root_name(node) == "context" for node in nodes):
                return False
        service = "rt.RESOLVE_PORTABLE_BEHAVIOR" if prefix == "resolver" else "rt.REDUCE_WALK_POLICY"
        return any(isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and node.func.attr == "observe_call"
            and ast.unparse(node.func.value) == "self.hooks"
            and [ast.unparse(argument) for argument in node.args] == [
                service, prefix + "_before", prefix + "_after",
            ] for node in _direct_function_nodes(install).nodes)

    @staticmethod
    def _is_private_name(name: str) -> bool:
        return (
            name in PRIVATE_PROOF_STATE_NAMES
            or name.startswith(PRIVATE_PROOF_STATE_PREFIXES)
        )

    @staticmethod
    def _function_product_c_facts(nodes: list[ast.AST]) -> tuple[bool, bool]:
        has_c_path = any(
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and (
                node.value.endswith(".c")
                or "/src/" in node.value
                or node.value.startswith("src/")
            )
            for node in nodes
        )
        has_source_read = any(
            isinstance(node, ast.Call)
            and _runtime_call_name(node) in ("open", "read_text", "read_bytes")
            for node in nodes
        )
        return has_c_path, has_source_read

    @staticmethod
    def _fault_hook_returns_value(
        function: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> bool:
        collector = _direct_function_nodes(function)
        return any(
            isinstance(node, ast.Return) and node.value is not None
            for node in collector.nodes
        )

    def audit(
        self,
        runner_scenario: str,
        *,
        public_actor_evidence: bool,
    ) -> list[str]:
        if self.error is not None:
            return [self.error]
        function_name = self.scenarios.get(runner_scenario)
        if function_name is None:
            return [f"runner scenario is not mapped by SCENARIOS: {runner_scenario}"]
        root = self.functions.get(function_name)
        if root is None:
            return [f"runner function is missing: {function_name}"]

        self.routing_errors.clear()
        pending: list[ast.FunctionDef | ast.AsyncFunctionDef] = [root]
        visited: set[int] = set()
        visited_module_values: set[tuple[str, str]] = set()
        issues: dict[str, str] = {}
        closure_has_c_path = False
        closure_has_source_read = False
        while pending:
            function = pending.pop()
            if id(function) in visited:
                continue
            visited.add(id(function))
            owner = self.function_owners.get(id(function), self)
            collector = _direct_function_nodes(function)
            fault_hook = function.name.startswith("fault_inject_")
            packaged_transport = (
                runner_scenario == "packaged_resolver_parity"
                and function.name in PACKAGED_SERVICE_TRANSPORT_FUNCTIONS
            )
            nested_by_name = {node.name: node for node in collector.nested}
            referenced_names = {
                node.id
                for node in collector.nodes
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
            }
            if not ((fault_hook and public_actor_evidence) or packaged_transport):
                for node in collector.nodes:
                    if not isinstance(node, ast.Attribute):
                        continue
                    for helper in self._attribute_functions(function, node):
                        if helper.name in PUBLIC_PROOF_TRANSPORT_FUNCTIONS and not (
                            helper is self.functions.get(helper.name)
                            and helper.name in self.trusted_public_transports
                        ):
                            issues.setdefault(
                                "public-transport-shadow",
                                "trusted public Actor transport is shadowed or "
                                f"modified in {function.name}:{function.lineno}",
                            )
                        if helper is self.functions.get(helper.name) and (
                            helper.name in self.trusted_public_transports
                            or helper.name in self.trusted_startup_transports
                        ):
                            continue
                        pending.append(helper)
            for name in referenced_names:
                if not (
                    (fault_hook and public_actor_evidence)
                    or packaged_transport
                ):
                    nested = nested_by_name.get(name)
                    if nested is not None:
                        pending.append(nested)
                    if name in PUBLIC_PROOF_TRANSPORT_FUNCTIONS:
                        lexical = self._lexical_functions(function, name)
                        if (
                            (
                                name in self.functions
                                and name not in self.trusted_public_transports
                            )
                            or any(
                                candidate is not self.functions.get(name)
                                for candidate in lexical
                            )
                        ):
                            issues.setdefault(
                                "public-transport-shadow",
                                "trusted public Actor transport is shadowed or "
                                f"modified in {function.name}:{function.lineno}",
                            )
                    elif name in STARTUP_IDENTITY_TRANSPORT_SHAPES:
                        if name not in self.trusted_startup_transports:
                            issues.setdefault(
                                "startup-transport-shadow",
                                "authenticated startup transport is shadowed or "
                                f"modified in {function.name}:{function.lineno}",
                            )
                    else:
                        pending.extend(self._lexical_functions(function, name))

                module_names = [name]
                while module_names:
                    module_name = module_names.pop()
                    module_key = (owner.module_name, module_name)
                    if module_key in visited_module_values:
                        continue
                    value = owner.module_values.get(module_name)
                    if value is None:
                        continue
                    visited_module_values.add(module_key)
                    if (
                        (fault_hook and public_actor_evidence)
                        or packaged_transport
                    ):
                        continue
                    for node in ast.walk(value):
                        if (
                            isinstance(node, ast.Name)
                            and isinstance(node.ctx, ast.Load)
                        ):
                            if (
                                self._is_private_name(node.id)
                                and not (fault_hook and public_actor_evidence)
                            ):
                                issues.setdefault(
                                    "private-state-offset",
                                    "private actor-policy or mount state is read "
                                    "by module value "
                                    f"{module_name}:{getattr(node, 'lineno', 0)}",
                                )
                            module_names.append(node.id)
                            if (
                                node.id not in PUBLIC_PROOF_TRANSPORT_FUNCTIONS
                                and node.id
                                    not in self.trusted_startup_transports
                            ):
                                pending.extend(
                                    self._lexical_functions(function, node.id)
                                )
                        if isinstance(node, ast.Call):
                            call_name = _runtime_call_name(node)
                            if (
                                call_name in PRIVATE_PROOF_STATE_CALLS
                                and not (fault_hook and public_actor_evidence)
                            ):
                                issues.setdefault(
                                    "private-state-offset",
                                    "private actor-policy or mount state is read "
                                    "by module value "
                                    f"{module_name}:{node.lineno}",
                                )

            has_c_path, has_source_read = self._function_product_c_facts(
                collector.nodes
            )
            closure_has_c_path |= has_c_path
            closure_has_source_read |= has_source_read
            if has_c_path and has_source_read:
                issues.setdefault(
                    "product-c-source-string",
                    f"product C source is read by {function.name}:{function.lineno}",
                )
            if fault_hook:
                if not public_actor_evidence:
                    issues.setdefault(
                        "fault-hook-public-proof",
                        "private fault injection lacks public Actor snapshot/trace "
                        f"proof in {function.name}:{function.lineno}",
                    )
                if self._fault_hook_returns_value(function):
                    issues.setdefault(
                        "fault-hook-result",
                        "fault injection returns data that pass criteria can consume "
                        f"in {function.name}:{function.lineno}",
                    )
                if any(
                    isinstance(node, ast.Global)
                    for node in collector.nodes
                ):
                    issues.setdefault(
                        "fault-hook-result",
                        "fault injection exports state through a module global "
                        f"in {function.name}:{function.lineno}",
                    )
                parameters = {
                    argument.arg
                    for argument in (
                        function.args.posonlyargs
                        + function.args.args
                        + function.args.kwonlyargs
                    )
                }
                local_names = parameters | {
                    target.id
                    for node in collector.nodes
                    if isinstance(node, (ast.Assign, ast.AnnAssign))
                    for target in (
                        node.targets if isinstance(node, ast.Assign)
                        else [node.target]
                    )
                    if isinstance(target, ast.Name)
                }
                exported_aliases = set(self.module_values) | {
                    name
                    for name in parameters
                    if name != "emu" and not name.startswith("_")
                }
                changed = True
                while changed:
                    changed = False
                    for node in collector.nodes:
                        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                            continue
                        value = node.value
                        if value is None or _root_name(value) not in exported_aliases:
                            continue
                        targets = (
                            node.targets if isinstance(node, ast.Assign)
                            else [node.target]
                        )
                        for target in targets:
                            if (
                                isinstance(target, ast.Name)
                                and target.id not in exported_aliases
                            ):
                                exported_aliases.add(target.id)
                                changed = True
                for node in collector.nodes:
                    target = None
                    if isinstance(node, ast.Subscript) and isinstance(
                        node.ctx, ast.Store
                    ):
                        target = node.value
                    elif isinstance(node, ast.Attribute) and isinstance(
                        node.ctx, ast.Store
                    ):
                        target = node.value
                    target_root = (
                        _root_name(target) if target is not None else None
                    )
                    if target_root is not None and target_root != "emu" and (
                        target_root in exported_aliases
                        or target_root not in local_names
                    ):
                        issues.setdefault(
                            "fault-hook-result",
                            "fault injection mutates caller or module state in "
                            f"{function.name}:{getattr(node, 'lineno', function.lineno)}",
                        )
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr in {
                            "append", "clear", "extend", "setdefault", "update",
                        }
                        and _root_name(node.func.value) is not None
                        and (
                            _root_name(node.func.value) in exported_aliases
                            or _root_name(node.func.value) not in local_names
                        )
                    ):
                        issues.setdefault(
                            "fault-hook-result",
                            "fault injection mutates caller or module state in "
                            f"{function.name}:{node.lineno}",
                        )
                if public_actor_evidence:
                    continue
            if packaged_transport:
                continue

            for node in collector.nodes:
                if owner is not self and isinstance(node, ast.Constant) \
                        and isinstance(node.value, int) and 0x02000000 <= node.value < 0x02400000 \
                        and function.name not in owner.trusted_abi_transports:
                    issues.setdefault(
                        "private-state-offset",
                        "imported proof embeds an untyped game RAM address in "
                        f"{function.name}:{node.lineno}",
                    )
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) \
                        and node.id in ABI_PROOF_TRANSPORT_SHAPES \
                        and node.id != "_public_abi_address":
                    parent = collector.parents.get(node)
                    if not isinstance(parent, ast.Call) or parent.func is not node:
                        issues.setdefault(
                            "public-abi-transport",
                            "public ABI reader cannot be aliased or exported "
                            f"from {function.name}:{node.lineno}",
                        )
                if isinstance(node, ast.Call):
                    call_name = _runtime_call_name(node)
                    if call_name in FORBIDDEN_PROOF_LANGUAGE_CALLS:
                        issues.setdefault(
                            "forbidden-proof-language",
                            "registered proof uses dynamic execution or lookup "
                            f"in {function.name}:{node.lineno}",
                        )
                    if owner is not self and call_name in {
                        "__import__", "import_module", "spec_from_file_location", "module_from_spec",
                    }:
                        issues.setdefault(
                            "local-proof-routing/dynamic-import",
                            "imported proof uses an unbounded dynamic import "
                            f"in {function.name}:{node.lineno}",
                        )
                    if call_name in PROCESS_LAUNCH_CALLS:
                        issues.setdefault(
                            "process-launch",
                            "registered proof launches a child process in "
                            f"{function.name}:{node.lineno}",
                        )
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "subprocess"
                    and node.func.attr in {
                        "Popen", "call", "check_call", "check_output", "run",
                    }
                    and any(
                        isinstance(child, ast.Constant)
                        and isinstance(child.value, str)
                        and (
                            child.value.endswith(".c")
                            or "/src/" in child.value
                            or child.value.startswith("src/")
                        )
                        for child in ast.walk(node)
                    )
                ):
                    issues.setdefault(
                        "product-c-source-string",
                        "registered proof launches a source-reading process in "
                        f"{function.name}:{node.lineno}",
                    )
                if (
                    isinstance(node, ast.Name) and self._is_private_name(node.id)
                    or isinstance(node, ast.Attribute) and self._is_private_name(node.attr)
                ):
                    issues.setdefault(
                        "private-state-offset",
                        "private actor-policy or mount state is read by "
                        f"{function.name}:{getattr(node, 'lineno', function.lineno)}",
                    )
                if isinstance(node, ast.Call):
                    name = _runtime_call_name(node)
                    if name in ABI_PROOF_TRANSPORT_SHAPES and name != "_public_abi_address" \
                            and not self._abi_call_is_typed(function, node):
                        issues.setdefault(
                            "public-abi-transport",
                            "public ABI buffer read has a modified reader or "
                            f"unproven pointer origin in {function.name}:{node.lineno}",
                        )
                    if (
                        name in RAW_ACTOR_MEMORY_PORTS
                        and not (function is self.functions.get(function.name)
                            and function.name in self.trusted_public_transports)
                        and function.name not in owner.trusted_abi_transports
                    ):
                        issues.setdefault(
                            "raw-actor-memory-port",
                            "registered proof bypasses typed public Actor "
                            f"transport in {function.name}:{node.lineno}",
                        )
                    if name in PRIVATE_PROOF_STATE_CALLS:
                        issues.setdefault(
                            "private-state-offset",
                            "private actor-policy or mount state is read by "
                            f"{function.name}:{node.lineno}",
                        )
                    if name in DIRECT_PROOF_STATE_WRITES:
                        issues.setdefault(
                            "direct-private-state-write",
                            "direct emulator state write is used by "
                            f"{function.name}:{node.lineno}",
                        )
                    if name is not None and name.startswith("fault_inject_"):
                        parent = collector.parents.get(node)
                        if not isinstance(parent, ast.Expr):
                            issues.setdefault(
                                "fault-hook-result",
                                "fault injection result is used by pass logic in "
                                f"{function.name}:{node.lineno}",
                            )
                if (
                    isinstance(node, ast.Subscript)
                    and _is_emulator_memory_store(node)
                ):
                    if isinstance(node.ctx, ast.Store):
                        issues.setdefault(
                            "direct-private-state-write",
                            "direct emulator state write is used by "
                            f"{function.name}:{node.lineno}",
                        )
                    elif owner is not self:
                        issues.setdefault(
                            "raw-actor-memory-port",
                            "imported proof reads an untyped emulator buffer in "
                            f"{function.name}:{node.lineno}",
                        )
            dynamic_memory_aliases = {
                target.id
                for node in collector.nodes
                if isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "getattr"
                and len(node.value.args) >= 2
                and isinstance(node.value.args[1], ast.Constant)
                and node.value.args[1].value in ("signed", "unsigned")
                for target in node.targets
                if isinstance(target, ast.Name)
            }
            if owner is not self:
                changed = True
                while changed:
                    changed = False
                    for node in collector.nodes:
                        if not isinstance(node, ast.Assign):
                            continue
                        if not (_is_emulator_memory_value(node.value)
                            or isinstance(node.value, ast.Name)
                            and node.value.id in dynamic_memory_aliases):
                            continue
                        for target in node.targets:
                            if isinstance(target, ast.Name) and target.id not in dynamic_memory_aliases:
                                dynamic_memory_aliases.add(target.id)
                                changed = True
            for node in collector.nodes:
                if (
                    isinstance(node, ast.Subscript)
                    and isinstance(node.value, ast.Name)
                    and node.value.id in dynamic_memory_aliases
                ):
                    kind = (
                        "direct-private-state-write"
                        if isinstance(node.ctx, ast.Store)
                        else "private-state-offset"
                    )
                    issues.setdefault(
                        kind,
                        "dynamic emulator memory alias is used by "
                        f"{function.name}:{node.lineno}",
                    )
        if closure_has_c_path and closure_has_source_read:
            issues.setdefault(
                "product-c-source-string",
                "product C source text is part of the registered runner path",
            )
        for error in sorted(self.routing_errors):
            issues.setdefault(f"local-proof-routing/{error}", error)
        return [f"{kind}: {detail}" for kind, detail in sorted(issues.items())]


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
    *,
    optional: Iterable[str] = (),
) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        _fail(errors, location, "must be an object")
        return None
    required_keys = set(required)
    expected = required_keys | set(optional)
    actual = set(value)
    missing = sorted(required_keys - actual)
    unknown = sorted(actual - expected)
    if missing:
        _fail(errors, location, f"missing keys: {', '.join(missing)}")
    if unknown:
        _fail(errors, location, f"unknown keys: {', '.join(unknown)}")
    return value


def _integer_matcher(value: Any, location: str, errors: list[str]) -> None:
    matcher = _object(
        value,
        location,
        (),
        errors,
        optional=("equals", "minimum", "maximum"),
    )
    if matcher is None:
        return
    if not matcher:
        _fail(errors, location, "must contain equals, minimum, or maximum")
        return
    parsed: dict[str, int] = {}
    for key in ("equals", "minimum", "maximum"):
        if key in matcher:
            result = _integer(
                matcher[key], f"{location}.{key}", errors, 0, 0xFFFFFFFF
            )
            if result is not None:
                parsed[key] = result
    if (
        "minimum" in parsed
        and "maximum" in parsed
        and parsed["minimum"] > parsed["maximum"]
    ):
        _fail(errors, location, "minimum must not exceed maximum")
    if "equals" in parsed and (
        ("minimum" in parsed and parsed["equals"] < parsed["minimum"])
        or ("maximum" in parsed and parsed["equals"] > parsed["maximum"])
    ):
        _fail(errors, location, "equals must be inside the minimum/maximum range")


def _event_predicate(
    value: Any, location: str, errors: list[str], *, with_id: bool
) -> str | None:
    required = ("id", "event") if with_id else ("event",)
    predicate = _object(
        value,
        location,
        required,
        errors,
        optional=("reason", "valueA", "valueB"),
    )
    if predicate is None:
        return None
    predicate_id = (
        _identifier(predicate.get("id"), f"{location}.id", errors)
        if with_id
        else None
    )
    _string(
        predicate.get("event"),
        f"{location}.event",
        errors,
        choices=SEMANTIC_EVENTS,
    )
    if "reason" in predicate:
        _string(
            predicate["reason"],
            f"{location}.reason",
            errors,
            choices=SEMANTIC_REASONS,
        )
    for key in ("valueA", "valueB"):
        if key in predicate:
            _integer_matcher(predicate[key], f"{location}.{key}", errors)
    return predicate_id


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
    allowed_placeholders = {"{python}", "{headless-python}", "{repo}"}
    for index, token in enumerate(command):
        placeholders = set(re.findall(r"\{[^{}]+\}", token))
        unknown = placeholders - allowed_placeholders
        if unknown:
            _fail(
                errors,
                f"{location}[{index}]",
                f"unknown placeholders: {', '.join(sorted(unknown))}",
            )
    if command and command[0] not in ("{python}", "{headless-python}"):
        _fail(
            errors,
            location,
            "must use {python} or the isolated {headless-python} runtime",
        )
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
            optional=("roleProof",),
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
        role_proof = capability.get("roleProof", [])
        if not isinstance(role_proof, list) or (
            "roleProof" in capability and not role_proof
        ):
            _fail(errors, f"{location}.roleProof", "must be a non-empty array")
            role_proof = []
        seen_role_levels: set[str] = set()
        for role_index, item in enumerate(role_proof):
            role_location = f"{location}.roleProof[{role_index}]"
            role_requirement = _object(
                item,
                role_location,
                ("proofLevel", "roles"),
                errors,
            )
            if role_requirement is None:
                continue
            role_level = _string(
                role_requirement.get("proofLevel"),
                f"{role_location}.proofLevel",
                errors,
                choices=("S3", "S4", "S5"),
            )
            required_roles = _string_list(
                role_requirement.get("roles"),
                f"{role_location}.roles",
                errors,
                choices=ROLES,
                allow_empty=False,
            )
            if role_level in seen_role_levels:
                _fail(
                    errors,
                    f"{role_location}.proofLevel",
                    "duplicates another role proof level",
                )
            elif role_level is not None:
                seen_role_levels.add(role_level)
            capability_roles = capability.get("roles")
            if isinstance(capability_roles, list) and required_roles is not None:
                for required_role in required_roles:
                    if required_role not in capability_roles:
                        _fail(
                            errors,
                            f"{role_location}.roles",
                            f"role is not owned by the capability: {required_role}",
                        )

    if errors:
        raise ValidationFailure("\n".join(errors))
    root["_checkIds"] = check_ids
    root["_capabilityIds"] = capability_ids
    root["_scenarioReferences"] = scenario_references
    return root


def _validate_verification_recipe(
    value: Any, location: str, errors: list[str], *, status: str | None = None
) -> None:
    """Describe proof scope without confusing a forced case with normal play.

    This validates declared scope, not the truth of a collector's declaration.
    A pending setup audit is an explicit review gap, never normal-play credit.
    """
    recipe = _object(
        value,
        location,
        (
            "kind", "expectationSource", "actor", "trigger", "observable",
            "setupAudit", "setupMutations", "limits",
        ),
        errors,
        optional=("control",),
    )
    if recipe is None:
        return
    kind = _string(recipe.get("kind"), f"{location}.kind", errors,
                   choices=VERIFICATION_KINDS)
    for field in ("expectationSource", "actor", "trigger", "observable"):
        _string(recipe.get(field), f"{location}.{field}", errors)
    source = recipe.get("expectationSource")
    if isinstance(source, str):
        source_path = Path(source.split("#", 1)[0])
        if (source_path.is_absolute() or ".." in source_path.parts
                or "\\" in source or not source_path.parts):
            _fail(errors, f"{location}.expectationSource",
                  "must name a repository-relative requirement or reference")
    audit = _string(recipe.get("setupAudit"), f"{location}.setupAudit", errors,
                    choices=("complete", "pending"))
    if kind == "normal-play" and audit != "complete" and status != "planned":
        _fail(errors, f"{location}.setupAudit",
              "normal-play needs a complete setup mutation audit")
    mutations = recipe.get("setupMutations")
    if not isinstance(mutations, list):
        _fail(errors, f"{location}.setupMutations", "must be an array")
        mutations = []
    for index, value in enumerate(mutations):
        mutation_location = f"{location}.setupMutations[{index}]"
        mutation = _object(value, mutation_location,
                           ("phase", "target", "change"), errors)
        if mutation is None:
            continue
        phase = _string(mutation.get("phase"), f"{mutation_location}.phase",
                        errors, choices=("before-observation", "during-observation"))
        target = _string(mutation.get("target"), f"{mutation_location}.target",
                         errors, choices=SETUP_MUTATION_TARGETS)
        _string(mutation.get("change"), f"{mutation_location}.change", errors)
        if kind == "normal-play" and (
            phase == "during-observation"
            or target in ("profile", "actors", "counters", "rng", "control-result")
        ):
            _fail(errors, mutation_location,
                  "normal-play cannot force actor, profile, counter, RNG, "
                  "or result state or mutate the case during observation")
    _string_list(recipe.get("limits"), f"{location}.limits", errors,
                 allow_empty=False)
    if kind == "observer-control":
        control = _object(recipe.get("control"), f"{location}.control",
                          ("boundary", "fault", "expectedFailure"), errors)
        if control is not None:
            _string(control.get("boundary"), f"{location}.control.boundary",
                    errors, choices=("live-runtime", "recorded-evidence"))
            for field in ("fault", "expectedFailure"):
                _string(control.get(field), f"{location}.control.{field}", errors)
    elif "control" in recipe:
        _fail(errors, f"{location}.control",
              "only observer-control declares a recorder fault")


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
        optional=("subjects", "roleProof", "verification"),
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
    proof_level = _string(
        root.get("proofLevel"),
        f"{path}.proofLevel",
        errors,
        choices=PROOF_LEVELS,
    )
    _integer(root.get("costTier"), f"{path}.costTier", errors, 0, 5)
    if proof_level in ("S3", "S4", "S5") or "verification" in root:
        _validate_verification_recipe(
            root.get("verification"), f"{path}.verification", errors, status=status
        )

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

    subjects = root.get("subjects", [])
    subjectless_service = root.get("id") in (
        "profile.resolve.packaged-rom-parity",
        "profile.condition.packaged-rom-evaluator",
    ) and (root.get("adapter") or {}).get("kind") == "devtools-test"
    if not isinstance(subjects, list) or ("subjects" in root and not subjects and not subjectless_service):
        _fail(errors, f"{path}.subjects", "must be a non-empty array")
        subjects = []
    subject_ids: list[str] = []
    for index, item in enumerate(subjects):
        location = f"{path}.subjects[{index}]"
        subject = _object(
            item,
            location,
            (
                "id",
                "species",
                "role",
                "acquisition",
                "minimum",
                "maximum",
                "motionActor",
                "requirePresentation",
            ),
            errors,
        )
        if subject is None:
            continue
        subject_id = _identifier(subject.get("id"), f"{location}.id", errors)
        if subject_id is not None:
            subject_ids.append(subject_id)
        _integer(subject.get("species"), f"{location}.species", errors, 1, 0xFFFF)
        _string(
            subject.get("role"),
            f"{location}.role",
            errors,
            choices=("WILD", "FOLLOWER", "MOUNTED", "SCRIPTED"),
        )
        _string(
            subject.get("acquisition"),
            f"{location}.acquisition",
            errors,
            choices=("spawn", "follower", "mount", "script"),
        )
        minimum = _integer(
            subject.get("minimum"), f"{location}.minimum", errors, 1, 32
        )
        maximum = _integer(
            subject.get("maximum"), f"{location}.maximum", errors, 1, 32
        )
        if minimum is not None and maximum is not None and minimum > maximum:
            _fail(errors, location, "minimum must not exceed maximum")
        for field in ("motionActor", "requirePresentation"):
            if not isinstance(subject.get(field), bool):
                _fail(errors, f"{location}.{field}", "must be a boolean")
    if len(set(subject_ids)) != len(subject_ids):
        _fail(errors, f"{path}.subjects", "subject ids must be unique")

    role_proof = root.get("roleProof", [])
    if not isinstance(role_proof, list) or ("roleProof" in root and not role_proof):
        _fail(errors, f"{path}.roleProof", "must be a non-empty array")
        role_proof = []
    seen_role_proof: set[tuple[str, str, str]] = set()
    for index, item in enumerate(role_proof):
        location = f"{path}.roleProof[{index}]"
        role_witness = _object(
            item,
            location,
            ("role", "claim", "measurement"),
            errors,
        )
        if role_witness is None:
            continue
        role = _string(
            role_witness.get("role"),
            f"{location}.role",
            errors,
            choices=ROLES,
        )
        claim = _string(
            role_witness.get("claim"),
            f"{location}.claim",
            errors,
            choices=RUNTIME_PROOF_CLAIMS,
        )
        measurement = _string(
            role_witness.get("measurement"),
            f"{location}.measurement",
            errors,
        )
        witness = (role or "", claim or "", measurement or "")
        if witness in seen_role_proof:
            _fail(errors, location, "duplicates another role proof witness")
        else:
            seen_role_proof.add(witness)

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
        optional=("orderedEvents", "eventCounts", "frameTiming"),
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
        ordered_ids: list[str] = []
        ordered_events = expect.get("orderedEvents", [])
        if not isinstance(ordered_events, list) or (
            "orderedEvents" in expect and not ordered_events
        ):
            _fail(errors, f"{path}.expect.orderedEvents", "must be a non-empty array")
            ordered_events = []
        for index, assertion in enumerate(ordered_events):
            assertion_id = _event_predicate(
                assertion,
                f"{path}.expect.orderedEvents[{index}]",
                errors,
                with_id=True,
            )
            if assertion_id is not None:
                ordered_ids.append(assertion_id)
        if len(set(ordered_ids)) != len(ordered_ids):
            _fail(
                errors,
                f"{path}.expect.orderedEvents",
                "assertion ids must be unique",
            )

        event_counts = expect.get("eventCounts", [])
        if not isinstance(event_counts, list) or (
            "eventCounts" in expect and not event_counts
        ):
            _fail(errors, f"{path}.expect.eventCounts", "must be a non-empty array")
            event_counts = []
        for index, assertion in enumerate(event_counts):
            location = f"{path}.expect.eventCounts[{index}]"
            count = _object(
                assertion,
                location,
                ("event", "minimum", "maximum"),
                errors,
                optional=("reason", "valueA", "valueB"),
            )
            if count is None:
                continue
            _event_predicate(
                {
                    key: count[key]
                    for key in ("event", "reason", "valueA", "valueB")
                    if key in count
                },
                location,
                errors,
                with_id=False,
            )
            minimum = _integer(
                count.get("minimum"), f"{location}.minimum", errors, 0, 0x7FFFFFFF
            )
            maximum = _integer(
                count.get("maximum"), f"{location}.maximum", errors, 0, 0x7FFFFFFF
            )
            if minimum is not None and maximum is not None and minimum > maximum:
                _fail(errors, location, "minimum must not exceed maximum")

        frame_timing = expect.get("frameTiming", [])
        if not isinstance(frame_timing, list) or (
            "frameTiming" in expect and not frame_timing
        ):
            _fail(errors, f"{path}.expect.frameTiming", "must be a non-empty array")
            frame_timing = []
        for index, assertion in enumerate(frame_timing):
            location = f"{path}.expect.frameTiming[{index}]"
            timing = _object(
                assertion,
                location,
                ("from", "to", "minimum", "maximum"),
                errors,
            )
            if timing is None:
                continue
            start = _identifier(timing.get("from"), f"{location}.from", errors)
            finish = _identifier(timing.get("to"), f"{location}.to", errors)
            minimum = _integer(
                timing.get("minimum"), f"{location}.minimum", errors, 0, 0x7FFFFFFF
            )
            maximum = _integer(
                timing.get("maximum"), f"{location}.maximum", errors, 0, 0x7FFFFFFF
            )
            for field, reference in (("from", start), ("to", finish)):
                if reference is not None and reference not in ordered_ids:
                    _fail(
                        errors,
                        f"{location}.{field}",
                        "must reference an orderedEvents assertion id",
                    )
            if minimum is not None and maximum is not None and minimum > maximum:
                _fail(errors, location, "minimum must not exceed maximum")
    _string(root.get("capture"), f"{path}.capture", errors, choices=CAPTURE_POLICIES)

    adapter = root.get("adapter")
    if isinstance(adapter, dict) and adapter.get("kind") == "devtools-test":
        shared = _object(adapter, f"{path}.adapter", ("kind", "test", "claims"), errors,
                         optional=("minimumFrames",))
        if status != "active":
            _fail(errors, f"{path}.adapter", "planned scenarios must not claim a live adapter")
        if proof_level not in ("S3", "S4", "S5"):
            _fail(errors, f"{path}.adapter", "shared devtools tests are runtime observations")
        if shared is not None:
            test_name = _identifier(shared.get("test"), f"{path}.adapter.test", errors)
            if test_name is not None and (".." in test_name or len(test_name) > 128):
                _fail(errors, f"{path}.adapter.test", "test must be a bounded registered name")
            claims = _string_list(shared.get("claims"), f"{path}.adapter.claims", errors,
                                  choices=RUNTIME_PROOF_CLAIMS, allow_empty=False)
            resolver_service = root.get("id") == "profile.resolve.packaged-rom-parity" \
                and test_name == root.get("id") and claims == ["profile-resolution"] \
                and proof_level == "S3" and subjects == []
            condition_service = root.get("id") == "profile.condition.packaged-rom-evaluator" \
                and test_name == root.get("id") and claims == ["profile-resolution"] \
                and proof_level == "S3" and subjects == [] \
                and (root.get("verification") or {}).get("kind") == "controlled-case"
            inspect_service = root.get("id") == "actor.inspect-current-and-stale" \
                and test_name == root.get("id") and claims == ["controlled-action"] \
                and proof_level == "S3" and subjects == [{"id": "mankey", "species": 56,
                    "role": "FOLLOWER", "acquisition": "follower", "minimum": 1, "maximum": 1,
                    "motionActor": False, "requirePresentation": True}] \
                and (root.get("verification") or {}).get("kind") == "controlled-case"
            population_service = root.get("id") == "population.land-surf-separation" \
                and test_name == root.get("id") and claims == ["terrain-selection"] \
                and proof_level == "S3" and subjects == [{"id": "mankey", "species": 56,
                    "role": "FOLLOWER", "acquisition": "follower", "minimum": 1, "maximum": 1,
                    "motionActor": False, "requirePresentation": True}] \
                and (root.get("verification") or {}).get("kind") == "controlled-case"
            if not (resolver_service or condition_service or inspect_service or population_service) \
                    and (not subjects or not claims or "live-actor-identity" not in claims):
                _fail(errors, f"{path}.subjects", "shared actor tests need structured live subjects")
            if fixture is None or not fixture.get("rom") or not fixture.get("save"):
                _fail(errors, f"{path}.fixture", "shared tests need explicit ROM and save")
            minimum = _integer(shared.get("minimumFrames", 5000 if proof_level == "S5" else 1),
                               f"{path}.adapter.minimumFrames", errors, 5000 if proof_level == "S5" else 1, 120000)
            frame_budget = (root.get("stop") or {}).get("frameBudget")
            if isinstance(minimum, int) and isinstance(frame_budget, int) and minimum > frame_budget:
                _fail(errors, f"{path}.adapter.minimumFrames", "must not exceed stop.frameBudget")
            # Capture is an optional human-view policy, never a proof input.
            # Shared S4 acceptance still requires its exact native measurements.
    elif adapter is None:
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
        adapter_optional_keys = (
            (
                "motionWindowCount", "commands", "result", "evidence",
                "claims", "minimumFrames", "visualArtifact",
            )
            if adapter_kind_value == "actor-observation"
            else ("claims", "minimumFrames", "visualArtifact")
        )
        adapter_object = _object(
            adapter,
            f"{path}.adapter",
            adapter_keys,
            errors,
            optional=adapter_optional_keys,
        )
        if adapter_object is not None:
            adapter_kind = _string(
                adapter_object.get("kind"),
                f"{path}.adapter.kind",
                errors,
                choices=("command-sequence", "actor-observation"),
            )
            if adapter_kind == "command-sequence" and expect is not None:
                semantic_assertions = (
                    "requiredEvents",
                    "forbiddenEvents",
                    "orderedEvents",
                    "eventCounts",
                    "frameTiming",
                )
                if any(expect.get(key) for key in semantic_assertions):
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
                _integer(
                    adapter_object.get("motionWindowCount", 1),
                    f"{path}.adapter.motionWindowCount",
                    errors,
                    1,
                    32,
                )
                if fixture is not None and fixture.get("rom") is None:
                    _fail(
                        errors,
                        f"{path}.fixture.rom",
                        "actor observation needs an explicit ROM fixture",
                    )
                executable_keys = {"commands", "result", "evidence"}
                present_executable_keys = executable_keys.intersection(adapter_object)
                if present_executable_keys and present_executable_keys != executable_keys:
                    _fail(
                        errors,
                        f"{path}.adapter",
                        "executable actor observation needs commands, result, and evidence",
                    )
                if present_executable_keys == executable_keys:
                    commands = adapter_object.get("commands")
                    if not isinstance(commands, list) or not commands:
                        _fail(
                            errors,
                            f"{path}.adapter.commands",
                            "must be a non-empty array",
                        )
                    else:
                        for index, command in enumerate(commands):
                            _command(
                                command,
                                f"{path}.adapter.commands[{index}]",
                                errors,
                            )
                    _string(
                        adapter_object.get("result"),
                        f"{path}.adapter.result",
                        errors,
                        choices=RESULT_KINDS,
                    )
                    evidence = _string(
                        adapter_object.get("evidence"),
                        f"{path}.adapter.evidence",
                        errors,
                    )
                    if evidence is not None:
                        evidence_path = Path(evidence)
                        if (
                            evidence_path.is_absolute()
                            or ".." in evidence_path.parts
                            or "\\" in evidence
                            or evidence_path.suffix != ".json"
                            or evidence_path.parts[:2]
                            != ("build", "overworld-evidence")
                        ):
                            _fail(
                                errors,
                                f"{path}.adapter.evidence",
                                "must be a repository-relative JSON file under build/overworld-evidence",
                            )
            executable = adapter_kind == "command-sequence" or (
                adapter_kind == "actor-observation"
                and "commands" in adapter_object
            )
            if executable and proof_level == "S5":
                commands = adapter_object.get("commands")
                if isinstance(commands, list) and len(commands) != 1:
                    _fail(
                        errors,
                        f"{path}.adapter.commands",
                        "S5 proof needs exactly one continuous runtime command",
                    )
            if (
                status == "active"
                and proof_level in ("S3", "S4", "S5")
                and not executable
            ):
                _fail(
                    errors,
                    f"{path}.adapter.commands",
                    "active S3-S5 proof must execute its current runtime fixture",
                )
            claims = adapter_object.get("claims")
            validated_claims = None
            if executable and proof_level in ("S3", "S4", "S5"):
                validated_claims = _string_list(
                    claims,
                    f"{path}.adapter.claims",
                    errors,
                    choices=RUNTIME_PROOF_CLAIMS,
                    allow_empty=False,
                )
                if adapter_object.get("result") != "json-passed":
                    _fail(
                        errors,
                        f"{path}.adapter.result",
                        "S3-S5 executable proof needs json-passed claims",
                    )
            elif claims is not None:
                validated_claims = _string_list(
                    claims,
                    f"{path}.adapter.claims",
                    errors,
                    choices=RUNTIME_PROOF_CLAIMS,
                    allow_empty=False,
                )
            if executable and proof_level == "S4" and validated_claims is not None:
                visual_claims = {
                    "feedback-effect",
                    "frame-pacing",
                    "rendered-motion",
                }
                if not visual_claims.intersection(validated_claims):
                    _fail(
                        errors,
                        f"{path}.adapter.claims",
                        "S4 proof needs rendered-motion, frame-pacing, or feedback-effect",
                    )
                artifact = _object(
                    adapter_object.get("visualArtifact"),
                    f"{path}.adapter.visualArtifact",
                    ("resultField", "path", "minimumBytes"),
                    errors,
                )
                if artifact is not None:
                    _identifier(
                        artifact.get("resultField"),
                        f"{path}.adapter.visualArtifact.resultField",
                        errors,
                    )
                    artifact_path = _string(
                        artifact.get("path"),
                        f"{path}.adapter.visualArtifact.path",
                        errors,
                    )
                    if artifact_path is not None and (
                        Path(artifact_path).is_absolute()
                        or ".." in Path(artifact_path).parts
                        or Path(artifact_path).suffix != ".png"
                        or Path(artifact_path).parts[:2]
                            != ("build", "overworld-artifacts")
                    ):
                        _fail(
                            errors,
                            f"{path}.adapter.visualArtifact.path",
                            "must be a PNG under build/overworld-artifacts",
                        )
                    _integer(
                        artifact.get("minimumBytes"),
                        f"{path}.adapter.visualArtifact.minimumBytes",
                        errors,
                        1,
                        0x7FFFFFFF,
                    )
            if executable and proof_level == "S5" and stop is not None:
                frame_budget = stop.get("frameBudget")
                if isinstance(frame_budget, int) and frame_budget < 5000:
                    _fail(
                        errors,
                        f"{path}.stop.frameBudget",
                        "S5 proof needs a bounded budget of at least 5000 frames",
                    )
                minimum_frames = _integer(
                    adapter_object.get("minimumFrames"),
                    f"{path}.adapter.minimumFrames",
                    errors,
                    5000,
                    1000000,
                )
                if (
                    isinstance(minimum_frames, int)
                    and isinstance(frame_budget, int)
                    and minimum_frames > frame_budget
                ):
                    _fail(
                        errors,
                        f"{path}.adapter.minimumFrames",
                        "must not exceed stop.frameBudget",
                    )
            if adapter_kind == "actor-observation":
                if (
                    isinstance(validated_claims, list)
                    and "live-actor-identity" in validated_claims
                    and not subjects
                ):
                    _fail(
                        errors,
                        f"{path}.subjects",
                        "live actor identity needs a structured subject contract",
                    )
                if subjects and (
                    not isinstance(validated_claims, list)
                    or "live-actor-identity" not in validated_claims
                ):
                    _fail(
                        errors,
                        f"{path}.adapter.claims",
                        "a structured subject needs live-actor-identity proof",
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
            elif subjects:
                _fail(
                    errors,
                    f"{path}.adapter.kind",
                    "structured subjects need controller-owned actor observation",
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


def validate_runtime_migration(document: Any, registry: dict[str, Any]) -> dict[str, Any]:
    """Retain every retired claim and measurement, including reviewed obsolete ones."""
    if not isinstance(document, dict) or set(document) != {
        "schemaVersion", "executionMethod", "legacyExecution", "requirements", "historicalScenarios"
    } or document.get("schemaVersion") != 1 or document.get("executionMethod") != "shared-devtools" \
            or document.get("legacyExecution") != "retired":
        raise ValidationFailure("invalid shared-devtools migration catalog")
    requirements = document.get("requirements")
    runners = registry.get("runners", {})
    legacy_runners = {
        key for key in runners
        if isinstance(key, str) and key.startswith("legacy.")
    }
    if not isinstance(requirements, dict) or set(requirements) != legacy_runners:
        raise ValidationFailure("migration catalog must retain every exact runtime requirement")
    history = document.get("historicalScenarios")
    if not isinstance(history, dict):
        raise ValidationFailure("migration catalog needs its complete historical scenario contracts")
    for key, item in requirements.items():
        fields = {
            "status", "verificationKind", "claims", "measurementContractSha256", "scenarios", "tests", "reason", "originRunner"
        }
        if isinstance(item, dict) and item.get("status") in ("superseded", "obsolete"):
            fields.add("review")
        if not isinstance(item, dict) or set(item) != fields:
            raise ValidationFailure(f"migration record has missing/unknown fields: {key}")
        expected_digest = hashlib.sha256(json.dumps(registry["measurementContracts"][key],
            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if item["verificationKind"] != registry["runnerKinds"][key] or item["claims"] != runners[key] \
                or item["measurementContractSha256"] != expected_digest:
            raise ValidationFailure(f"migration record changed its original measurement contract: {key}")
        if not isinstance(item["originRunner"], str) or "::" not in item["originRunner"] \
                or key != "legacy." + item["originRunner"].split("::")[-1].replace("_", "-"):
            raise ValidationFailure(f"migration record lost its exact historical origin: {key}")
        if item["status"] not in ("pending", "ported", "superseded", "obsolete") or not isinstance(item["reason"], str) or not item["reason"].strip():
            raise ValidationFailure(f"migration record needs an explicit state and reason: {key}")
        for field in ("scenarios", "tests"):
            names = item[field]
            if not isinstance(names, list) or any(not isinstance(name, str) or not ID_PATTERN.fullmatch(name) for name in names) \
                    or len(set(names)) != len(names):
                raise ValidationFailure(f"migration {field} must be distinct named contracts: {key}")
        if item["status"] == "pending" and item["tests"]:
            raise ValidationFailure(f"pending requirement cannot claim a completed test mapping: {key}")
        if item["status"] == "ported" and not item["tests"]:
            raise ValidationFailure(f"ported requirement needs exact shared test mappings: {key}")
        if item["status"] == "superseded" and item["tests"]:
            raise ValidationFailure(f"superseded requirement must use replacement tests: {key}")
        if item["status"] == "obsolete" and item["tests"]:
            raise ValidationFailure(f"obsolete requirement cannot claim a current test mapping: {key}")
    expected_history = {name for item in requirements.values() for name in item["scenarios"]}
    if set(history) != expected_history or any(not isinstance(value, dict) or value.get("id") != key
                                             for key, value in history.items()):
        raise ValidationFailure("migration catalog lost a complete historical scenario contract")
    _validate_runtime_supersessions(document, registry)
    _validate_runtime_obsolescence(document)
    return document


def resolve_runtime_migration_targets(document: dict[str, Any], key: str) -> list[str]:
    """Resolve reviewed replacements, not proof acceptance. Validate the catalog first."""
    requirements = document["requirements"]
    def visit(current, ancestors):
        if current not in requirements:
            raise ValidationFailure("unknown migration replacement: " + str(current))
        if current in ancestors:
            raise ValidationFailure("migration supersession cycle: " + current)
        item = requirements[current]
        if item["status"] == "obsolete":
            return set()
        if item["status"] != "superseded":
            return {current}
        result = set()
        for row in item["review"]["coverage"]:
            result.update(visit(row["replacementRequirement"], ancestors | {current}))
        return result
    return sorted(visit(key, set()))


def _validate_runtime_obsolescence(document):
    """Require a dated, evidence-backed review when the product contract ended."""
    for key, item in document["requirements"].items():
        if item["status"] != "obsolete":
            continue
        review = item["review"]
        fields = {"reviewer", "reviewedAt", "reason", "removedAssumption", "currentContract", "evidence"}
        if not isinstance(review, dict) or set(review) != fields \
                or any(not isinstance(review.get(name), str) or not review[name].strip()
                       for name in fields - {"evidence"}):
            raise ValidationFailure("migration obsolescence needs a complete named review: " + key)
        try:
            stamp = date.fromisoformat(review["reviewedAt"])
            if stamp.isoformat() != review["reviewedAt"] or stamp > date.today():
                raise ValidationFailure("migration obsolescence review date differs: " + key)
        except ValueError:
            raise ValidationFailure("migration obsolescence review date differs: " + key)
        evidence = review["evidence"]
        if not isinstance(evidence, list) or len(evidence) < 2 or len(evidence) != len(set(evidence)) \
                or any(not isinstance(value, str) or not value.strip() for value in evidence):
            raise ValidationFailure("migration obsolescence needs distinct source and runtime evidence: " + key)


def _validate_runtime_supersessions(document, registry):
    requirements = document["requirements"]
    contracts = registry["measurementContracts"]
    def fail(key, reason):
        raise ValidationFailure("migration supersession " + reason + ": " + key)
    for key, item in requirements.items():
        if item["status"] != "superseded":
            continue
        review = item["review"]
        if not isinstance(review, dict) or set(review) != {"reviewer", "reviewedAt", "reason", "coverage"} \
                or any(not isinstance(review.get(k), str) or not review[k].strip()
                       for k in ("reviewer", "reviewedAt", "reason")):
            fail(key, "needs a named review and reason")
        try:
            stamp = date.fromisoformat(review["reviewedAt"])
            if stamp.isoformat() != review["reviewedAt"] or stamp > date.today():
                fail(key, "review date differs")
        except ValueError:
            fail(key, "review date differs")
        original = {(claim, row["name"]): row for claim, rows in contracts[key].items() for row in rows}
        coverage = review["coverage"]
        if not isinstance(coverage, list) or not coverage:
            fail(key, "coverage missing")
        covered = set()
        for row in coverage:
            if not isinstance(row, dict) or set(row) != {"claim", "measurement", "replacementRequirement",
                    "replacementClaim", "replacementMeasurement", "reason"} \
                    or any(not isinstance(v, str) or not v.strip() for v in row.values()):
                fail(key, "measurement mapping differs")
            source = (row["claim"], row["measurement"])
            target = row["replacementRequirement"]
            if source not in original or source in covered:
                fail(key, "source measurement missing or duplicated")
            covered.add(source)
            if target not in requirements or row["replacementClaim"] != row["claim"] \
                    or requirements[target]["verificationKind"] != item["verificationKind"]:
                fail(key, "replacement claim or kind differs")
            replacements = [r for r in contracts[target].get(row["replacementClaim"], [])
                            if r["name"] == row["replacementMeasurement"]]
            # Renaming/combining tests cannot silently weaken an existing bound,
            # required object key, validator, or semantic claim. A real contract
            # change remains a separate reviewed requirement edit.
            without_name = lambda r: {k:v for k,v in r.items() if k != "name"}
            if len(replacements) != 1 or without_name(replacements[0]) != without_name(original[source]):
                fail(key, "replacement weakens or changes required measurement")
        if covered != set(original):
            fail(key, "leaves required measurements uncovered")
    # Check the graph only after every mapping's shape has been checked.
    for key, item in requirements.items():
        if item["status"] != "superseded":
            continue
        for target in resolve_runtime_migration_targets(document, key):
            endpoint = requirements[target]
            if endpoint["status"] != "ported":
                fail(key, "replacement is still pending")
            for test in endpoint["tests"]:
                spec = registry.get("sharedTests", {}).get(test, {})
                if target not in spec.get("requirements", []) \
                        or not set(endpoint["claims"]).issubset(spec.get("claims", [])):
                    fail(key, "replacement shared test is not registered")


def cross_validate(
    manifest: dict[str, Any],
    scenarios: dict[str, dict[str, Any]],
    repo: Path | None = None,
    *,
    audit_runtime_proof_sources: bool = False,
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
    checks_by_id = {check["id"]: check for check in manifest["checks"]}
    for capability in manifest["capabilities"]:
        available_levels = {
            checks_by_id[check_id]["proofLevel"]
            for check_id in capability["checks"]
            if checks_by_id[check_id]["proofLevel"] not in ("S3", "S4", "S5")
        }
        available_levels.update(
            scenarios[scenario_id]["proofLevel"]
            for scenario_id in capability["scenarios"]
            if scenario_id in scenarios
            and scenarios[scenario_id].get("verification", {}).get("kind")
                != "observer-control"
        )
        for required_level in capability["minimumProof"]:
            if required_level not in available_levels:
                required_source = (
                    "scenario"
                    if required_level in ("S3", "S4", "S5")
                    else "check or scenario"
                )
                errors.append(
                    f"capability {capability['id']}: minimum proof "
                    f"{required_level} has no linked {required_source}"
                )
    if repo is not None:
        proof_registry_path = repo / "tools/overworld/runtime_proof_registry.json"
        proof_registry = load_json_document(proof_registry_path)
        shared_migration = None
        if proof_registry.get("executionMethod") == "shared-devtools":
            if proof_registry.get("migration") != "tools/overworld/runtime_proof_migration.json":
                errors.append("shared runtime proof needs the canonical migration catalog")
            else:
                try:
                    shared_migration = validate_runtime_migration(
                        load_json_document(repo / proof_registry["migration"]), proof_registry)
                except (OSError, ValueError, KeyError, ValidationFailure) as error:
                    errors.append(str(error))
        registered_runners = (
            proof_registry.get("runners")
            if isinstance(proof_registry, dict)
            and proof_registry.get("schemaVersion") == 2
            else None
        )
        measurement_contracts = (
            proof_registry.get("measurementContracts")
            if isinstance(proof_registry, dict)
            and proof_registry.get("schemaVersion") == 2
            else None
        )
        runner_kinds = proof_registry.get("runnerKinds") \
            if isinstance(proof_registry, dict) else None
        if not isinstance(registered_runners, dict):
            errors.append(
                "runtime proof registry must contain schemaVersion 2 and runners"
            )
            registered_runners = {}
        if not isinstance(measurement_contracts, dict):
            errors.append(
                "runtime proof registry must contain measurementContracts"
            )
            measurement_contracts = {}
        elif set(measurement_contracts) != set(registered_runners):
            errors.append(
                "runtime proof runner and measurement-contract keys differ"
            )
        if not isinstance(runner_kinds, dict):
            errors.append("runtime proof registry must contain runnerKinds")
            runner_kinds = {}
        elif set(runner_kinds) != set(registered_runners):
            errors.append("runtime proof runner and kind keys differ")
        for runner_key, claims in registered_runners.items():
            if (
                not isinstance(runner_key, str)
                or not isinstance(claims, list)
                or not claims
                or any(not isinstance(claim, str) for claim in claims)
                or len(set(claims)) != len(claims)
                or any(claim not in RUNTIME_PROOF_CLAIMS for claim in claims)
            ):
                errors.append(
                    f"runtime proof registry has invalid runner: {runner_key}"
                )
                continue
            if runner_kinds.get(runner_key) not in VERIFICATION_KINDS:
                errors.append(
                    f"runtime proof runner has an invalid verification kind: {runner_key}"
                )
            runner_contract = measurement_contracts.get(runner_key)
            if (
                not isinstance(runner_contract, dict)
                or set(runner_contract) != set(claims)
            ):
                errors.append(
                    f"runtime proof measurement claims differ: {runner_key}"
                )
                continue
            for claim, measurements in runner_contract.items():
                if (
                    not isinstance(measurements, list)
                    or not measurements
                    or any(not isinstance(item, dict) for item in measurements)
                ):
                    errors.append(
                        f"runtime proof measurements are invalid: {runner_key}::{claim}"
                    )
                    continue
                names = [item.get("name") for item in measurements]
                if (
                    any(not isinstance(name, str) or not name for name in names)
                    or len(set(names)) != len(names)
                    or any(
                        item.get("operator")
                            not in ("eq", "ne", "lt", "lte", "gt", "gte")
                        or item.get("type")
                            not in ("integer", "array", "object", "string")
                        or set(item)
                            - {
                                "name", "operator", "type", "expected",
                                "minimum", "maximum", "minItems", "requiredKeys",
                                "validator", "fromRole", "toRole",
                                "aspect", "requiredCount", "minimumTotal",
                                "distance", "caseCount",
                            }
                        or item.get("validator") not in (
                            "meaningful-observation",
                            "actor-handle-current",
                            "positive-identical-values",
                            "live-object-identity-flags",
                            "public-role-transition-v1",
                            "acceleration-terminal-series-v1",
                            "stationary-single-crash-v1",
                            "complete-motion-observation-v1",
                            "stream-target-reached-v1",
                            "blocked-state-unchanged-v1",
                            "terminal-boundary-target-v1",
                            "hop-arc-parabola-v1",
                            "nearest-diagonal-choice-v1",
                            "stable-selector-identity-v1",
                            "mounted-frame-matrix-v1",
                            "contiguous-elapsed-v1",
                            "all-render-samples-synced-v1",
                            "population-refill-v1",
                            "teleport-timing-matrix-v1",
                            "turn-skid-recovery-v1",
                            "completed-route-v1",
                            "warp-destination-v1",
                            "wild-teleport-terminal-v1",
                            "motion-sample-counts-v1",
                            "motion-elapsed-schedules-v1",
                            "packaged-resolver-parity-v1",
                        )
                        for item in measurements
                    )
                ):
                    errors.append(
                        f"runtime proof measurement contract is invalid: "
                        f"{runner_key}::{claim}"
                    )
                for item in measurements:
                    if not any(
                        key in item
                        for key in ("expected", "minimum", "maximum", "validator")
                    ):
                        errors.append(
                            "runtime proof measurement has no independent "
                            f"acceptance rule: {runner_key}::{claim}::{item.get('name')}"
                        )
                    if (
                        item.get("validator") == "meaningful-observation"
                        and not any(
                            key in item
                            for key in ("expected", "minimum", "maximum")
                        )
                    ):
                        errors.append(
                            "runtime proof measurement has no independent "
                            f"acceptance rule: {runner_key}::{claim}::"
                            f"{item.get('name')}"
                        )
        for scenario_id, scenario in scenarios.items():
            recipe = scenario.get("verification")
            shared_adapter = scenario.get("adapter") or {}
            shared_test = None
            registered = None
            if shared_adapter.get("kind") == "devtools-test":
                try:
                    from tools.overworld.devtools_test_contract import validate_test
                    test_path = repo / "tests/overworld/test-recipes" / (shared_adapter["test"] + ".json")
                    test_bytes = test_path.read_bytes()
                    shared_test = validate_test(json.loads(test_bytes))
                    registered = proof_registry.get("sharedTests", {}).get(shared_adapter["test"])
                    if not isinstance(registered, dict):
                        raise ValueError("shared scenario has no reviewed test registration")
                    if registered.get("recipeSha256") != hashlib.sha256(test_bytes).hexdigest():
                        raise ValueError("shared scenario recipe differs from its reviewed hash")
                    expected_kind = {"normal": "normal-play", "prepared": "controlled-case", "observer-control": "observer-control"}[shared_test["mode"]]
                    # This exact movement adapter audits prepared setup separately
                    # and forbids interventions during the measured normal route.
                    # Other prepared tests cannot acquire normal-play credit.
                    if shared_test["mode"] == "prepared" and (
                            (registered.get("evaluator") == "unmounted-cadence-v1"
                             and registered.get("requirements") == ["legacy.unmounted-long-travel"])
                            or (registered.get("evaluator") == "unmounted-game-cadence-v1"
                                and registered.get("requirements") == ["current.unmounted-game-cadence"])
                            ):
                        expected_kind = "normal-play"
                    if (shared_test["id"] != shared_adapter["test"]
                            or registered.get("mode") != shared_test["mode"]
                            or registered.get("requirements") != shared_test["requirements"]
                            or registered.get("proofLevel") != scenario["proofLevel"]
                            or registered.get("claims") != shared_adapter["claims"]
                            or recipe.get("kind") != expected_kind):
                        raise ValueError("shared scenario scope differs from the reviewed recipe/registration")
                    if (scenario["fixture"]["rom"] != shared_test["fixture"]["rom"]
                            or scenario["fixture"]["save"]["path"] != shared_test["fixture"]["save"]
                            or scenario["stop"]["frameBudget"] != shared_test["budgets"]["maxFrames"]
                            or shared_adapter.get("minimumFrames", 1) != registered.get("minimumObservedFrames")
                            or shared_test["budgets"]["minObservedFrames"] < registered["minimumObservedFrames"]):
                        raise ValueError("shared scenario fixture/frame limits differ from its reviewed test")
                    declared_subjects = [{key: subject[key] for key in ("id", "species", "role")} for subject in scenario["subjects"]]
                    recipe_subjects = [{key: subject[key] for key in ("id", "species", "role")} for subject in shared_test["subjects"]]
                    if declared_subjects != recipe_subjects or any(subject["minimum"] != 1 or subject["maximum"] != 1
                            or subject["requirePresentation"] is not True for subject in scenario["subjects"]):
                        raise ValueError("shared scenario subjects differ from the exact recipe identities")
                except (OSError, ValueError, KeyError, TypeError) as error:
                    errors.append(f"scenario {scenario_id}: {error}")
            if isinstance(recipe, dict):
                source_path = recipe.get("expectationSource", "").split("#", 1)[0]
                if not (repo / source_path).is_file():
                    errors.append(
                        f"scenario {scenario_id}: expectation source does not exist: "
                        f"{source_path}"
                    )
                adapter = scenario.get("adapter") or {}
                for command in adapter.get("commands", []):
                    if len(command) < 2 or "--scenario" not in command:
                        continue
                    index = command.index("--scenario")
                    if index + 1 >= len(command):
                        continue
                    runner_key = f"{command[1]}::{command[index + 1]}"
                    if runner_kinds.get(runner_key) != recipe.get("kind"):
                        errors.append(
                            f"scenario {scenario_id}: verification kind differs from "
                            f"registered runner {runner_key}"
                        )
            role_witnesses = scenario.get("roleProof", [])
            if not role_witnesses:
                continue
            if isinstance(recipe, dict) and recipe.get("kind") == "observer-control":
                errors.append(
                    f"scenario {scenario_id}: observer-control cannot supply gameplay role proof"
                )
                continue
            adapter = scenario.get("adapter")
            command_adapter = (
                isinstance(adapter, dict)
                and adapter.get("kind") == "actor-observation"
                and bool(adapter.get("commands"))
            )
            shared_devtools_adapter = (
                isinstance(adapter, dict)
                and adapter.get("kind") == "devtools-test"
                and isinstance(shared_test, dict)
                and isinstance(registered, dict)
                and bool(registered.get("requirements"))
            )
            if (
                scenario.get("status") != "active"
                or scenario.get("proofLevel") not in ("S3", "S4", "S5")
                or not (command_adapter or shared_devtools_adapter)
            ):
                errors.append(
                    f"scenario {scenario_id}: explicit role proof needs an "
                    "active executable runtime actor observation"
                )
                continue
            if shared_devtools_adapter:
                runner_keys = list(registered["requirements"])
            else:
                runner_keys = []
                for command in adapter["commands"]:
                    script = command[1] if len(command) > 1 else None
                    scenario_index = (
                        command.index("--scenario")
                        if "--scenario" in command
                        else -1
                    )
                    runner_scenario = (
                        command[scenario_index + 1]
                        if scenario_index >= 0
                        and scenario_index + 1 < len(command)
                        else None
                    )
                    runner_keys.append(
                        f"{script}::{runner_scenario}"
                        if script is not None and runner_scenario is not None
                        else None
                    )
            for witness in role_witnesses:
                role = witness["role"]
                claim = witness["claim"]
                measurement = witness["measurement"]
                if claim not in adapter.get("claims", []):
                    errors.append(
                        f"scenario {scenario_id}: role proof claim is not "
                        f"declared by the adapter: {claim}"
                    )
                    continue
                for runner_key in runner_keys:
                    contract = measurement_contracts.get(runner_key, {})
                    entries = contract.get(claim, []) \
                        if isinstance(contract, dict) else []
                    matches = [
                        entry for entry in entries
                        if isinstance(entry, dict)
                        and entry.get("name") == measurement
                    ]
                    if len(matches) != 1:
                        errors.append(
                            f"scenario {scenario_id}: role proof measurement "
                            f"is not registered exactly once for {runner_key}: "
                            f"{claim}::{measurement}"
                        )
                        continue
                    entry = matches[0]
                    fixed_string_witness = (
                        entry.get("operator") == "eq"
                        and entry.get("type") == "string"
                        and entry.get("expected") == role.upper()
                    )
                    public_transition_witness = (
                        entry.get("operator") == "eq"
                        and entry.get("type") == "object"
                        and entry.get("validator")
                            == "public-role-transition-v1"
                        and entry.get("fromRole") == role.upper()
                    )
                    if not (
                        fixed_string_witness or public_transition_witness
                    ):
                        errors.append(
                            f"scenario {scenario_id}: role proof measurement "
                            f"does not fix the expected {role} role for "
                            f"{runner_key}: {claim}::{measurement}"
                        )
        # Registry declarations own result shape. The controller checks the
        # returned claims, names, operators and types; source construction may
        # move between helper functions without changing the proof contract.
        # Actor identity is checked for every structured subject, not by a
        # species-specific list of measurement names.
        proof_source_audits: dict[str, RuntimeProofSourceAudit] = {}
        audited_proof_paths: set[tuple[str, str]] = set()
        for scenario_id, scenario in (
            scenarios.items() if audit_runtime_proof_sources else ()
        ):
            adapter = scenario.get("adapter")
            if shared_migration is not None and scenario.get("proofLevel") in ("S3", "S4", "S5") \
                    and isinstance(adapter, dict) and adapter.get("kind") != "devtools-test":
                # Historical declarations are retained as migration gaps, not
                # executable adapters. control.py rejects them before dispatch.
                continue
            if (
                scenario.get("status") != "active"
                or scenario.get("proofLevel") not in ("S3", "S4", "S5")
                or not isinstance(adapter, dict)
                or not adapter.get("commands")
            ):
                continue
            declared_claims = adapter.get("claims")
            for command in adapter["commands"]:
                script = command[1] if len(command) > 1 else None
                scenario_index = (
                    command.index("--scenario")
                    if "--scenario" in command
                    else -1
                )
                runner_scenario = (
                    command[scenario_index + 1]
                    if scenario_index >= 0 and scenario_index + 1 < len(command)
                    else None
                )
                runner_key = (
                    f"{script}::{runner_scenario}"
                    if script is not None and runner_scenario is not None
                    else None
                )
                registered_claims = registered_runners.get(runner_key)
                if registered_claims is None:
                    errors.append(
                        f"scenario {scenario_id}: runtime runner is not registered: "
                        f"{runner_key or command}"
                    )
                elif registered_claims != declared_claims:
                    errors.append(
                        f"scenario {scenario_id}: runner claims differ for "
                        f"{runner_key}: expected {declared_claims}, "
                        f"registered {registered_claims}"
                    )
                if (
                    runner_key is None
                    or runner_scenario is None
                    or not isinstance(script, str)
                    or (scenario_id, runner_key) in audited_proof_paths
                ):
                    continue
                audited_proof_paths.add((scenario_id, runner_key))
                script_path = Path(script)
                if script_path.is_absolute() or ".." in script_path.parts:
                    errors.append(
                        f"scenario {scenario_id}: runtime proof source escapes "
                        f"the repository: {script}"
                    )
                    continue
                source_path = repo / script_path
                try:
                    if script not in proof_source_audits:
                        proof_source_audits[script] = RuntimeProofSourceAudit(
                            source_path.read_text(), repo=repo,
                        )
                    source_audit = proof_source_audits[script]
                except OSError as error:
                    errors.append(
                        f"scenario {scenario_id}: runtime proof source cannot "
                        f"be read: {error}"
                    )
                    continue
                for issue in source_audit.audit(
                        runner_scenario,
                        public_actor_evidence=
                            scenario_uses_public_actor_evidence(scenario)):
                    errors.append(
                        f"scenario {scenario_id}: private runtime proof "
                        f"dependency in {runner_key}: {issue}"
                    )
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
            fields = behavior_schema.get("fields")
            reserved_only_feature_ids = set()
            if isinstance(fields, list):
                used_feature_ids = {
                    field.get("featureId")
                    for field in fields
                    if isinstance(field, dict) and field.get("reserved") is not True
                }
                reserved_only_feature_ids = {
                    field.get("featureId")
                    for field in fields
                    if isinstance(field, dict) and field.get("reserved") is True
                } - used_feature_ids
            missing_capabilities = sorted(
                set(schema_feature_ids)
                - reserved_only_feature_ids
                - capability_ids
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
