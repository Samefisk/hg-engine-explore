#!/usr/bin/env python3
"""Generate the human overworld feature table from the canonical manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "tools/overworld/system_features.yaml"
DOCUMENT = REPO / "documentation/overworld-system/verification.md"
BEGIN = "<!-- BEGIN GENERATED OVERWORLD FEATURE MAP -->"
END = "<!-- END GENERATED OVERWORLD FEATURE MAP -->"


def render() -> str:
    data = json.loads(MANIFEST.read_text())
    capabilities = data.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        raise ValueError("feature manifest has no capabilities")
    lines = [
        "| Capability | Owner | Roles | Minimum proof |",
        "| --- | --- | --- | --- |",
    ]
    for capability in capabilities:
        lines.append(
            "| {title} (`{id}`) | {owner} | {roles} | {proof} |".format(
                title=capability["title"],
                id=capability["id"],
                owner=capability["owner"],
                roles=", ".join(capability["roles"]),
                proof=", ".join(capability["minimumProof"]),
            )
        )
    return "\n".join(lines)


def expected_document(current: str) -> str:
    if current.count(BEGIN) != 1 or current.count(END) != 1:
        raise ValueError("verification document must contain one feature-map marker pair")
    before, remainder = current.split(BEGIN, 1)
    _, after = remainder.split(END, 1)
    return f"{before}{BEGIN}\n\n{render()}\n\n{END}{after}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when the generated table is stale instead of writing it",
    )
    args = parser.parse_args()
    current = DOCUMENT.read_text()
    expected = expected_document(current)
    if current == expected:
        print(f"up to date: {DOCUMENT.relative_to(REPO)}")
        return 0
    if args.check:
        print(f"stale: {DOCUMENT.relative_to(REPO)}")
        return 1
    DOCUMENT.write_text(expected)
    print(f"updated: {DOCUMENT.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
