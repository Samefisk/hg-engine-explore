#!/usr/bin/env python3
"""Import, generate, or check the named overworld behavior catalog."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "scripts/overworld_behavior_profile_viewer.py"


def load_authoring_module():
    spec = importlib.util.spec_from_file_location("overworld_behavior_authoring", VIEWER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {VIEWER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate positional C compatibility data from named profile authoring data."
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--import-c",
        action="store_true",
        help="one-time migration: import the expanded C values into the named catalog",
    )
    action.add_argument(
        "--check",
        action="store_true",
        help="fail if the catalog and generated C/header are not synchronized",
    )
    args = parser.parse_args()
    authoring = load_authoring_module()

    if args.import_c:
        authoring.write_behavior_data_source(
            authoring.BEHAVIOR_DATA_SOURCE.read_text(),
            authoring.BEHAVIOR_DATA_HEADER.read_text(),
        )
        print(f"Imported {authoring.BEHAVIOR_CATALOG_SOURCE.relative_to(ROOT)}")
        return 0

    if not authoring.BEHAVIOR_CATALOG_SOURCE.exists():
        parser.error("named catalog is missing; run with --import-c once")
    catalog = authoring.json.loads(authoring.BEHAVIOR_CATALOG_SOURCE.read_text())
    authoring.validate_behavior_catalog(catalog)
    current_source = authoring.BEHAVIOR_DATA_SOURCE.read_text()
    current_header = authoring.BEHAVIOR_DATA_HEADER.read_text()
    generated_source = authoring.render_behavior_catalog(catalog, current_source)
    generated_header = authoring.render_behavior_catalog_header(
        current_header, catalog, generated_source
    )

    if args.check:
        stale = []
        if generated_source != current_source:
            stale.append(str(authoring.BEHAVIOR_DATA_SOURCE.relative_to(ROOT)))
        if generated_header != current_header:
            stale.append(str(authoring.BEHAVIOR_DATA_HEADER.relative_to(ROOT)))
        if stale:
            print("Generated behavior data is stale: " + ", ".join(stale))
            return 1
        print("Named behavior catalog and generated C data are synchronized")
        return 0

    authoring.write_behavior_catalog(catalog)
    print(f"Generated {authoring.BEHAVIOR_DATA_SOURCE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
