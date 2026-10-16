#!/usr/bin/env python3
"""Build the local source explorer from its human-readable Markdown map."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
KINDS = {"System", "Module", "Adapter", "Rule", "Event", "Contract", "Support", "Tool"}
LINK_TYPES = {"supplies", "requests", "reads", "updates", "builds", "checks"}


def validate_profile_facts(nodes):
    """Reject copied profile facts that disagree with the authoring sources."""
    schema = json.loads(
        (ROOT / "tools/overworld/schemas/behavior-authoring-v5.schema.json").read_text()
    )
    catalog = json.loads((ROOT / "data/overworld_behavior_profiles.json").read_text())
    definitions = schema.get("$defs") if isinstance(schema, dict) else None
    classification = definitions.get("profileClassification") if isinstance(definitions, dict) else None
    values = classification.get("enum") if isinstance(classification, dict) else None
    if (not isinstance(values, list) or not values
            or any(not isinstance(value, str) or not value for value in values)
            or len(values) != len(set(values))):
        raise ValueError("invalid V5 schema: profileClassification.enum must be a nonempty list of unique names")
    profiles = catalog.get("profiles") if isinstance(catalog, dict) else None
    if (not isinstance(profiles, list)
            or any(not isinstance(profile, dict)
                   or not isinstance(profile.get("id"), str) or not profile["id"]
                   for profile in profiles)):
        raise ValueError("invalid profile catalog: profiles must be a list of objects with named IDs")
    labels = {
        value: value.replace("-", "/").title()
        for value in values
    }
    expected_order = " → ".join(labels.values()) + "."
    block = next((node for node in nodes if node["id"] == "classifications"), None)
    if block is None or block["summary"] != expected_order:
        raise ValueError(f"profile order differs from the V5 schema; expected: {expected_order}")
    matches = [profile for profile in profiles if profile["id"] == "waddle"]
    if len(matches) != 1:
        raise ValueError(f"the profile catalog must contain exactly one Waddle profile; found {len(matches)}")
    waddle = matches[0]
    if not isinstance(waddle.get("classification"), str) or waddle["classification"] not in labels:
        raise ValueError("the profile catalog has no classified Waddle profile")
    expected_class = labels[waddle["classification"]]
    claim = re.search(r"\bWaddle uses the ([^.]+) classification\.", block["detail"])
    if claim is None or claim[1] != expected_class:
        raise ValueError(f"Waddle classification differs from the catalog; expected: {expected_class}")


def source_path(value):
    target = value.split("#", 1)[0]
    resolved = (ROOT / target).resolve()
    if not target or not resolved.is_relative_to(ROOT) or not resolved.exists():
        raise ValueError(f"missing or out-of-scope source: {value}")
    return value


def parse_map(markdown):
    nodes = []
    edges = []
    current = None
    reading_sources = False
    reading_links = False
    for line in markdown.splitlines():
        heading = re.fullmatch(r"## ([a-z][a-z0-9-]*): (.+)", line)
        if heading:
            current = {"id": heading[1], "label": heading[2], "sources": [], "detail": []}
            nodes.append(current)
            reading_sources = reading_links = False
            continue
        if line.startswith("## "):
            current = None
            reading_links = line == "## Connections"
            continue
        if reading_links and line.startswith("|"):
            cells = [part.strip() for part in line.strip("|").split("|")]
            if cells[0] == "From" or cells[0].startswith("---"):
                continue
            if len(cells) != 5:
                raise ValueError(f"expected five connection columns: {line}")
            edges.append(dict(zip(("from", "to", "type", "meaning", "source"), cells)))
        if current is None:
            continue
        field = re.fullmatch(r"(Parent|Kind|Grid|Summary|Rule): (.+)", line)
        if field:
            key = field[1].lower()
            current[key] = field[2].strip("`")
            reading_sources = False
        elif line == "Sources:":
            reading_sources = True
        elif reading_sources and line.startswith("- `") and line.endswith("`"):
            current["sources"].append(source_path(line[3:-1]))
        elif line.strip():
            reading_sources = False
            current["detail"].append(line)
    by_id = {}
    for node in nodes:
        if node["id"] in by_id:
            raise ValueError(f"duplicate block: {node['id']}")
        by_id[node["id"]] = node
        for key in ("parent", "kind", "grid", "summary", "rule"):
            if key not in node:
                raise ValueError(f"missing {key} in {node['id']}")
        if node["kind"] not in KINDS or not node["sources"] or not node["detail"]:
            raise ValueError(f"incomplete block: {node['id']}")
        if not re.fullmatch(r"[0-9]+,[0-9]+", node["grid"]):
            raise ValueError(f"invalid grid in {node['id']}")
        node["grid"] = [int(value) for value in node["grid"].split(",")]
        node["detail"] = "\n".join(node["detail"])
    if not nodes or nodes[0]["id"] != "system" or nodes[0]["parent"] != "none":
        raise ValueError("expected one system root")
    cells = set()
    for node in nodes:
        if node["id"] == "system":
            continue
        cell = (node["parent"], *node["grid"])
        if cell in cells:
            raise ValueError(f"duplicate grid position in {node['parent']}")
        cells.add(cell)
        seen = {node["id"]}
        parent = node["parent"]
        while parent != "system":
            if parent in seen or parent not in by_id:
                raise ValueError(f"invalid parent tree at {node['id']}")
            seen.add(parent)
            parent = by_id[parent]["parent"]
    edge_keys = set()
    for edge in edges:
        if edge["from"] not in by_id or edge["to"] not in by_id:
            raise ValueError(f"unknown connection endpoint: {edge}")
        if edge["type"] not in LINK_TYPES or edge["from"] == edge["to"] or not edge["meaning"]:
            raise ValueError(f"invalid connection: {edge}")
        key = (edge["from"], edge["to"], edge["type"], edge["meaning"])
        if key in edge_keys:
            raise ValueError(f"duplicate connection: {key}")
        edge_keys.add(key)
        source_path(edge["source"])
    if not edges:
        raise ValueError("empty connection map")
    linked = {edge[key] for edge in edges for key in ("from", "to")}
    for node in nodes:
        if node["id"] != "system" and node["kind"] != "Contract" and node["id"] not in linked:
            if not any(child["parent"] == node["id"] for child in nodes):
                raise ValueError(f"unlinked leaf: {node['id']}")
    validate_profile_facts(nodes)
    return {"nodes": nodes, "edges": edges, "sourceHash": hashlib.sha256(markdown.encode()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate without writing; reject stale HTML")
    args = parser.parse_args()
    try:
        data = parse_map((HERE / "map.md").read_text())
        template = (HERE / "template.html").read_text()
        if template.count("@@MAP_DATA@@") != 1:
            raise ValueError("expected one map-data placeholder")
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
        output = template.replace("@@MAP_DATA@@", payload)
        target = HERE / "index.html"
        if args.check:
            if not target.exists() or target.read_text() != output:
                raise ValueError("index.html is stale; run this builder without --check")
        else:
            target.write_text(output)
        print(f"{'checked' if args.check else 'built'} explorer: {len(data['nodes'])} blocks, {len(data['edges'])} relations; sources valid")
        return 0
    except (ValueError, OSError) as error:
        print(f"explorer: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
