#!/usr/bin/env python3
"""Report every checked-in consumer of the legacy overworld Active model.

The report is read-only and deterministic. It discovers tracked repository
files through Git, classifies each legacy finding, and adds semantic catalog
records for links that cannot be reviewed safely from text matches alone.

Exit codes:
  0: every finding is classified; no forbidden finding in forbidden mode
  1: one or more findings are unclassified, or the inventory cannot run
  2: --forbid-legacy found a CP7-forbidden consumer
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = Path("data/overworld_behavior_profiles.json")
SELF_PATH = Path("scripts/report_overworld_active_profile_migration.py")
TEST_PATH = Path("tools/overworld/test_report_overworld_active_profile_migration.py")
MAPPING_PATH = Path(
    "tools/overworld/fixtures/conditional_profile_migration_v1.json"
)

CLASSIFICATIONS = (
    "condition_input",
    "profile_response",
    "presentation_state",
    "compatibility_adapter",
    "migration_data",
    "test",
    "dead_code",
)

SCANNED_SUFFIXES = {
    ".c", ".h", ".html", ".inc", ".js", ".json", ".mjs", ".py", ".s",
    ".toml", ".yaml", ".yml",
}

EXCLUDED_PREFIXES = (
    "documentation/",
    ".codex-reference/",
)


def _is_authoritative_overworld_path(path: Path) -> bool:
    value = path.as_posix()
    return (
        value in {
            "data/overworld_behavior_profiles.json",
            "data/OverworldWildBehaviorData.c",
        }
        or value.startswith((
            "include/overworld",
            "lib/overworld/",
            "src/overworld_",
            "tools/overworld/",
            "tools/overworld-viewer-v2/",
            "tests/overworld/",
            "design_previews/overworld-tools-v2/",
        ))
        or (value.startswith("scripts/") and "overworld" in path.name.lower())
        or path.name.lower().startswith("overworld_")
    )


@dataclass(frozen=True)
class PatternSpec:
    kind: str
    pattern: re.Pattern[str]
    forbidden_at_cp7: bool


def _pattern(kind: str, expression: str, forbidden: bool = True) -> PatternSpec:
    return PatternSpec(kind, re.compile(expression), forbidden)


# These expressions name the old behavior model. They intentionally do not
# match a bare "active": actor liveness, active motion, overlays, and UI focus
# are separate concepts. Binary expressions are constrained by profile/result
# words so unrelated numeric values do not enter the report.
PATTERNS = (
    _pattern("active_profile_reference", r"\b(?:activeProfile|active_profile)\b"),
    _pattern(
        "default_active_binding",
        r"\b(?:defaultActiveApplication|OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_DEFAULT_ACTIVE)\b",
    ),
    _pattern(
        "active_profile_mask",
        r"\bOW_WILD_BEHAVIOR_OVERRIDE3_ACTIVE_PROFILE\b",
    ),
    _pattern(
        "conditional_state_model",
        r"\b(?:conditionalStates?|conditional_states?|"
        r"OWBD_CONDITIONAL_STATE(?:_STORAGE)?_COUNT)\b",
    ),
    _pattern(
        "conditional_state_record",
        r"\bOverworldWildBehaviorConditionalState\b",
    ),
    _pattern(
        "old_condition_context",
        r"\bconditionTerrainMask\b",
    ),
    _pattern(
        "alert_condition",
        r"\b(?:alertState|alertRange|alertness|alertChance|"
        r"OverworldWildSpawns_IsPlayerInAlert[A-Za-z0-9_]*|"
        r"OverworldWildSpawns_TryStartSpotEmote)\b",
        forbidden=False,
    ),
    _pattern(
        "alert_presentation",
        r"\b(?:alertEmote|alertTime|alertSpecialAction|movementEmoteEndStates|"
        r"OverworldWildSpawns_(?:Cancel|Get|Start|Tick)[A-Za-z0-9_]*SpotEmote[A-Za-z0-9_]*)\b",
        forbidden=False,
    ),
    _pattern(
        "attentive_field",
        r"\b(?:attentive(?:[A-Z][A-Za-z0-9_]*)?|ATTENTIVE(?:_[A-Z0-9]+)+)\b",
    ),
    _pattern(
        "active_lane_response",
        r"\b(?:movementStyle|targetSelector|activeReaction)\b",
    ),
    _pattern(
        "active_lane_member",
        r"\bOverworldWildBehaviorProfileData\s+active\b|"
        r"\bprofile(?:->|\.)active\b",
    ),
    _pattern(
        "active_lane_enum",
        r"\bBEHAVIOR_RESOLUTION_LANE_ACTIVE\b",
    ),
    _pattern(
        "runtime_active_state",
        r"\bOW_WILD_(?:SPAWNER_)?SPOT_STATE_ACTIVE\b",
    ),
    _pattern(
        "runtime_active_counter",
        r"\b(?:movementActiveSteps|movementFrameDrivenActiveMask|movementSpotCooldowns)\b",
    ),
    _pattern(
        "runtime_active_transition",
        r"\bOverworldWildSpawns_[A-Za-z0-9_]*(?:ActiveState|ActiveMovement)[A-Za-z0-9_]*\b",
    ),
    _pattern(
        "active_lane_selector",
        r"\bOverworldWildSpawns_GetBehaviorStateLane\b",
    ),
    _pattern(
        "profile_binary_record",
        r"\b(?:OverworldWildBehaviorProfileSizeMustRemain216Bytes|"
        r"BehaviorResolverProfileSizeMustRemain216)\b|"
        r"sizeof\(OverworldWildBehaviorProfile\)\s*==\s*216|"
        r"\bPROFILE_BYTES\b[^\n]*\b216\b|"
        r"\b(?:profile|resolved|lane)[A-Za-z0-9_]*[^\n]{0,48}\b216\b|"
        r"\b216\b[^\n]{0,48}\b(?:profile|resolved|lane)[A-Za-z0-9_]*|"
        r"\[:216\]",
    ),
    _pattern(
        "primitive_binary_record",
        r"sizeof\(OverworldWildBehaviorPrimitives\)\s*==\s*11|"
        r"\bPRIMITIVE_BYTES\b[^\n]*\b11\b|"
        r"\bprimitivesHex\b[^\n]{0,48}\b11\b|"
        r"\b11\b[^\n]{0,48}\bprimitivesHex\b",
    ),
    _pattern(
        "resolve_result_binary_record",
        r"sizeof\(BehaviorResolveResult\)\s*==\s*256|"
        r"\bresultHex\b[^\n]{0,48}\b256\b|"
        r"\b256\b[^\n]{0,48}\bresultHex\b|"
        r"offsetof\(BehaviorResolveResult\s*,|"
        r"\bresult\[(?:218|222|236|240|244|248)(?::|\])|"
        r"struct\.unpack_from\([^\n]*\bresult\b[^\n]*\b236\b",
    ),
    _pattern(
        "three_lane_package",
        r"PROFILE_SIZE\s*\*\s*3|"
        r"\(0\s*,\s*72\s*,\s*144\)|"
        r"[\[(](?:\"owner\"|'owner')\s*,\s*(?:\"active\"|'active')\s*,\s*"
        r"(?:\"tired\"|'tired')[\])]|"
        r"\blane_names\b[^\n]*\bActive\b|"
        r"decode_native_profile\([^\n]*\blane\s*=\s*1\b|"
        r"\"lanes\"\s*:\s*\[\s*\"profile\"\s*,\s*\"owner\"\s*,\s*"
        r"\"active\"\s*,\s*\"tired\"\s*\]",
    ),
    _pattern(
        "resolved_profile_record_consumer",
        r"\bOverworldWildBehaviorProfile\b",
        forbidden=False,
    ),
    _pattern(
        "primitive_record_consumer",
        r"\bOverworldWildBehaviorPrimitives\b",
        forbidden=False,
    ),
    _pattern(
        "resolve_result_record_consumer",
        r"\bBehaviorResolveResult\b",
        forbidden=False,
    ),
    _pattern(
        "resolution_trace_record_consumer",
        r"\bBehaviorResolution(?:Step|Trace)\b",
        forbidden=False,
    ),
    _pattern(
        "behavior_version_record",
        r"\b(?:OVERWORLD_WILD_BEHAVIOR_(?:OVERLAY|DATA)_VERSION|"
        r"OW_BEHAVIOR_SCHEMA_(?:BLOB_)?VERSION|BEHAVIOR_DATA_VERSION|blobVersion)\b|"
        r"\b(?:BehaviorResolveResult|compact|public)[^\n]{0,32}\bv\d+\b",
        forbidden=False,
    ),
    _pattern(
        "catalog_version_record",
        r"\bcatalogVersion\b",
        forbidden=False,
    ),
)


def _is_test_path(path: Path) -> bool:
    parts = path.parts
    name = path.name
    return (
        "tests" in parts
        or "fixtures" in parts
        or name.startswith("test_")
        or name.startswith("verify_")
        or "_harness" in path.stem
    )


def _is_workshop_or_adapter(path: Path) -> bool:
    value = path.as_posix()
    return (
        value == "scripts/overworld_behavior_profile_viewer.py"
        or value.startswith("tools/overworld-viewer-v2/")
        or value.startswith("tools/overworld/devtools")
        or value.startswith("tools/overworld/control")
    )


def _is_schema_or_generator(path: Path) -> bool:
    value = path.as_posix()
    return (
        value == "tools/overworld/behavior_schema.json"
        or value == "tools/overworld/behavior_schema.py"
        or value == "tools/overworld/generated/behavior_schema.json"
        or value.startswith("tools/overworld/schemas/behavior-authoring-")
        or path.name.startswith("generate_overworld_behavior_")
    )


def _is_runtime_source(path: Path) -> bool:
    value = path.as_posix()
    return (
        value.startswith(("include/overworld", "lib/overworld/", "src/overworld_"))
        or (value.startswith("src/") and path.name.lower().startswith("overworld_"))
    )


def classify(path: Path, kind: str) -> str | None:
    """Return one migration class, or None when ownership is not known."""
    value = path.as_posix()
    if _is_test_path(path):
        return "test"
    if value.startswith("design_previews/"):
        return "dead_code"
    if path == CATALOG_PATH:
        return "migration_data"
    if _is_schema_or_generator(path):
        return "migration_data"
    if _is_workshop_or_adapter(path):
        return "compatibility_adapter"
    if kind in {
        "profile_binary_record",
        "primitive_binary_record",
        "resolve_result_binary_record",
        "three_lane_package",
        "active_lane_enum",
        "conditional_state_record",
        "resolved_profile_record_consumer",
        "primitive_record_consumer",
        "resolve_result_record_consumer",
        "resolution_trace_record_consumer",
        "behavior_version_record",
        "catalog_version_record",
    }:
        return "compatibility_adapter"
    if value == "data/OverworldWildBehaviorData.c":
        return "compatibility_adapter"
    if kind in {"conditional_state_model", "old_condition_context", "alert_condition"}:
        if _is_runtime_source(path) and not value.startswith("include/"):
            return "condition_input"
        if value.startswith(("include/overworld", "scripts/", "tools/overworld/")):
            return "compatibility_adapter"
    if kind in {"alert_presentation", "runtime_active_state", "runtime_active_counter",
                "runtime_active_transition"}:
        if _is_runtime_source(path):
            return "presentation_state"
    if kind in {"active_profile_reference", "default_active_binding", "active_profile_mask"}:
        if _is_runtime_source(path):
            return "profile_response"
        if value.startswith(("scripts/", "tools/overworld/")):
            return "migration_data"
    if kind in {"attentive_field", "active_lane_response", "active_lane_member",
                "active_lane_selector"}:
        if _is_runtime_source(path):
            return "profile_response"
        if value.startswith(("scripts/", "tools/overworld/")):
            return "compatibility_adapter"
    return None


def discover_source_files(root: Path) -> list[Path]:
    command = [
        "git", "-C", str(root), "ls-files", "-z",
        "--cached", "--others", "--exclude-standard",
    ]
    result = subprocess.run(command, capture_output=True, check=False)
    if result.returncode:
        message = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(f"git worktree-file discovery failed: {message}")
    files = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        value = raw.decode(errors="strict")
        path = Path(value)
        if path in {SELF_PATH, TEST_PATH}:
            continue
        if value.startswith(EXCLUDED_PREFIXES):
            continue
        if path.suffix.lower() not in SCANNED_SUFFIXES:
            continue
        if not _is_authoritative_overworld_path(path):
            continue
        files.append(path)
    if not files:
        raise RuntimeError("worktree-file discovery returned no scannable overworld files")
    return sorted(files, key=lambda item: item.as_posix())


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _finding(
    *,
    path: Path,
    line: int,
    symbol: str,
    kind: str,
    classification: str | None,
    forbidden_at_cp7: bool,
    excerpt: str,
    details: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "path": path.as_posix(),
        "line": line,
        "symbol": symbol,
        "kind": kind,
        "classification": classification,
        "forbiddenAtCp7": forbidden_at_cp7,
        "excerpt": excerpt.strip(),
        "details": details or {},
    }


def scan_text(path: Path, text: str) -> list[dict[str, object]]:
    findings = []
    for line_number, line in enumerate(text.splitlines(), 1):
        for spec in PATTERNS:
            for match in spec.pattern.finditer(line):
                symbol = match.group(0)
                findings.append(_finding(
                    path=path,
                    line=line_number,
                    symbol=symbol,
                    kind=spec.kind,
                    classification=classify(path, spec.kind),
                    forbidden_at_cp7=spec.forbidden_at_cp7,
                    excerpt=line,
                ))
    return findings


def _literal_offsets(text: str, literal: str) -> list[int]:
    return [match.start() for match in re.finditer(re.escape(literal), text)]


def _next_literal_offset(text: str, literal: str, start: int) -> int:
    offset = text.find(literal, start)
    if offset < 0:
        raise ValueError(f"catalog text does not contain expected literal after offset {start}: {literal}")
    return offset


def scan_catalog(root: Path) -> list[dict[str, object]]:
    absolute = root / CATALOG_PATH
    text = absolute.read_text()
    try:
        catalog = json.loads(text)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"cannot parse {CATALOG_PATH}: {error}") from error

    profiles = {profile["id"]: profile for profile in catalog.get("profiles", [])}
    applications = {item["id"]: item for item in catalog.get("applications", [])}
    if not profiles or not applications:
        raise RuntimeError("behavior catalog has no profiles or applications")

    findings = []
    active_offsets = iter(_literal_offsets(text, '"activeProfile"'))
    active_targets: dict[str, list[str]] = {}
    for profile in catalog["profiles"]:
        authored = profile.get("fields", {}).get("activeProfile")
        if authored is None:
            continue
        try:
            offset = next(active_offsets)
        except StopIteration as error:
            raise RuntimeError("catalog activeProfile text count is lower than parsed data") from error
        application_id = str(authored.get("value"))
        if application_id not in applications:
            raise RuntimeError(
                f"profile {profile['id']} names missing Active application {application_id}"
            )
        response_profile = str(applications[application_id]["profile"])
        active_targets.setdefault(response_profile, []).append(str(profile["id"]))
        findings.append(_finding(
            path=CATALOG_PATH,
            line=_line_number(text, offset),
            symbol=str(profile["id"]),
            kind="catalog_active_profile_reference",
            classification="migration_data",
            forbidden_at_cp7=True,
            excerpt=f"{profile['id']} -> {application_id} -> {response_profile}",
            details={
                "sourceProfile": profile["id"],
                "application": application_id,
                "responseProfile": response_profile,
            },
        ))

    runtime = catalog.get("runtimeBindings", {})
    default_application = runtime.get("defaultActiveApplication")
    if default_application is not None:
        if not isinstance(default_application, str) or default_application not in applications:
            raise RuntimeError("runtimeBindings.defaultActiveApplication is invalid")
        default_profile = str(applications[default_application]["profile"])
        active_targets.setdefault(default_profile, []).append("runtime-default")
        default_offset = _next_literal_offset(text, '"defaultActiveApplication"', 0)
        findings.append(_finding(
            path=CATALOG_PATH,
            line=_line_number(text, default_offset),
            symbol="runtimeBindings.defaultActiveApplication",
            kind="catalog_default_active_binding",
            classification="migration_data",
            forbidden_at_cp7=True,
            excerpt=f"runtime default -> {default_application} -> {default_profile}",
            details={
                "application": default_application,
                "responseProfile": default_profile,
            },
        ))

    conditional_states = catalog.get("conditionalStates", [])
    if not isinstance(conditional_states, list):
        raise RuntimeError("catalog conditionalStates is not a list")
    search_offset = (
        _next_literal_offset(text, '"conditionalStates"', 0)
        if "conditionalStates" in catalog
        else 0
    )
    for state in conditional_states:
        state_id = str(state.get("id", ""))
        if not state_id:
            raise RuntimeError("catalog conditionalStates entry has no id")
        search_offset = _next_literal_offset(text, f'"id": "{state_id}"', search_offset)
        findings.append(_finding(
            path=CATALOG_PATH,
            line=_line_number(text, search_offset),
            symbol=state_id,
            kind="catalog_conditional_state_entry",
            classification="migration_data",
            forbidden_at_cp7=True,
            excerpt=(
                f"{state_id}: {state.get('parentApplication')} -> "
                f"{state.get('application')}"
            ),
            details={
                "parentApplication": state.get("parentApplication"),
                "application": state.get("application"),
                "terrainMask": state.get("terrainMask"),
                "terrainOverrideMask": state.get("terrainOverrideMask"),
                "minMovementSpeed": state.get("minMovementSpeed"),
                "maxMovementSpeed": state.get("maxMovementSpeed"),
            },
        ))
        search_offset += 1

    for profile_id, sources in sorted(active_targets.items()):
        profile = profiles.get(profile_id)
        if profile is None:
            raise RuntimeError(f"Active response profile is missing: {profile_id}")
        offset = _next_literal_offset(text, f'"id": "{profile_id}"', 0)
        findings.append(_finding(
            path=CATALOG_PATH,
            line=_line_number(text, offset),
            symbol=profile_id,
            kind="catalog_active_response_profile",
            classification="profile_response",
            forbidden_at_cp7=True,
            excerpt=f"Active response profile {profile_id}",
            details={
                "referencedBy": sorted(sources),
                "localFields": sorted(profile.get("fields", {})),
            },
        ))
    return findings


def mapped_legacy_sources(root: Path) -> set[str]:
    """Return the reviewed CP6 source-profile mappings when present."""

    path = root / MAPPING_PATH
    if not path.is_file():
        return set()
    try:
        mapping = json.loads(path.read_text())
    except json.JSONDecodeError as error:
        raise RuntimeError(f"cannot parse {MAPPING_PATH}: {error}") from error
    entries = mapping.get("mappings")
    if mapping.get("version") != 1 or not isinstance(entries, list):
        raise RuntimeError(f"{MAPPING_PATH} has an unsupported shape")
    sources = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or not isinstance(
            entry.get("legacySourceProfile"), str
        ):
            raise RuntimeError(
                f"{MAPPING_PATH} mapping {index} has no legacySourceProfile"
            )
        sources.append(entry["legacySourceProfile"])
    if len(sources) != len(set(sources)):
        raise RuntimeError(f"{MAPPING_PATH} has duplicate legacy source profiles")
    return set(sources)


def build_inventory(
    root: Path = ROOT,
    files: Sequence[Path] | None = None,
    include_catalog_semantics: bool = True,
) -> dict[str, object]:
    root = root.resolve()
    discovered = list(files) if files is not None else discover_source_files(root)
    findings: list[dict[str, object]] = []
    scanned = []
    for path in sorted(discovered, key=lambda item: item.as_posix()):
        relative = path if not path.is_absolute() else path.relative_to(root)
        absolute = root / relative
        if not absolute.is_file():
            raise RuntimeError(f"worktree scan target is missing: {relative}")
        try:
            text = absolute.read_text()
        except UnicodeDecodeError as error:
            raise RuntimeError(f"worktree scan target is not text: {relative}") from error
        scanned.append(relative.as_posix())
        findings.extend(scan_text(relative, text))
    if include_catalog_semantics and CATALOG_PATH in discovered:
        findings.extend(scan_catalog(root))

    unique: dict[tuple[object, ...], dict[str, object]] = {}
    for finding in findings:
        key = (
            finding["path"], finding["line"], finding["kind"],
            finding["symbol"], json.dumps(finding["details"], sort_keys=True),
        )
        unique[key] = finding
    ordered = sorted(
        unique.values(),
        key=lambda item: (
            str(item["path"]), int(item["line"]), str(item["kind"]), str(item["symbol"]),
        ),
    )
    if not ordered:
        raise RuntimeError("inventory found no legacy or compatibility target")
    for index, finding in enumerate(ordered, 1):
        finding["id"] = f"CP0-{index:04d}"

    by_classification = Counter(
        str(item["classification"]) if item["classification"] is not None else "unclassified"
        for item in ordered
    )
    by_kind = Counter(str(item["kind"]) for item in ordered)
    unclassified = [item["id"] for item in ordered if item["classification"] is None]
    forbidden = [item["id"] for item in ordered if item["forbiddenAtCp7"]]
    mapped_sources = mapped_legacy_sources(root)
    migration_sources = [
        item for item in ordered
        if item["kind"] == "catalog_active_profile_reference"
    ]
    mapped_source_findings = [
        item["id"] for item in migration_sources
        if item["details"]["sourceProfile"] in mapped_sources
    ]
    unmapped_source_findings = [
        item["id"] for item in migration_sources
        if item["details"]["sourceProfile"] not in mapped_sources
    ]
    return {
        "schemaVersion": 1,
        "source": "Git worktree files plus semantic named-catalog inspection",
        "classifications": list(CLASSIFICATIONS),
        "scan": {
            "fileCount": len(scanned),
            "files": scanned,
            "excludedSelf": [SELF_PATH.as_posix(), TEST_PATH.as_posix()],
        },
        "summary": {
            "findingCount": len(ordered),
            "unclassifiedCount": len(unclassified),
            "forbiddenAtCp7Count": len(forbidden),
            "mappedLegacySourceCount": len(mapped_source_findings),
            "unmappedLegacySourceCount": len(unmapped_source_findings),
            "byClassification": dict(sorted(by_classification.items())),
            "byKind": dict(sorted(by_kind.items())),
        },
        "unclassifiedFindingIds": unclassified,
        "forbiddenFindingIds": forbidden,
        "mappedLegacySourceFindingIds": mapped_source_findings,
        "unmappedLegacySourceFindingIds": unmapped_source_findings,
        "findings": ordered,
    }


def write_json(report: dict[str, object], output: Path | None, compact: bool) -> None:
    encoded = json.dumps(
        report,
        sort_keys=True,
        separators=(",", ":") if compact else None,
        indent=None if compact else 2,
    ) + "\n"
    if output is None:
        sys.stdout.write(encoded)
        return
    output.write_text(encoded)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inventory the legacy overworld Active/attentive profile model."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="repository root; defaults to the script's repository",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="write JSON to this path instead of stdout",
    )
    parser.add_argument(
        "--compact",
        action="store_true",
        help="emit compact JSON",
    )
    parser.add_argument(
        "--forbid-legacy",
        action="store_true",
        help="exit 2 when any CP7-forbidden legacy finding remains",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        report = build_inventory(args.root)
        write_json(report, args.output, args.compact)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"active-profile migration inventory failed: {error}", file=sys.stderr)
        return 1
    if report["summary"]["unclassifiedCount"]:
        return 1
    if args.forbid_legacy and report["summary"]["forbiddenAtCp7Count"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
