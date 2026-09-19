#!/usr/bin/env python3
"""Generate or check C compatibility data from the named behavior catalog."""

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
        "--check",
        action="store_true",
        help="fail if the catalog and generated C/header are not synchronized",
    )
    parser.add_argument("--catalog", type=Path, help="named catalog input")
    parser.add_argument("--source-template", type=Path, help="compatibility C template")
    parser.add_argument("--header-template", type=Path, help="compatibility header template")
    parser.add_argument("--source-output", type=Path, help="generated compatibility C output")
    parser.add_argument("--header-output", type=Path, help="generated compatibility header output")
    args = parser.parse_args()
    authoring = load_authoring_module()

    catalog_path = (args.catalog or authoring.BEHAVIOR_CATALOG_SOURCE).resolve()
    source_template = (args.source_template or authoring.BEHAVIOR_DATA_SOURCE).resolve()
    header_template = (args.header_template or authoring.BEHAVIOR_DATA_HEADER).resolve()
    if (args.source_output is None) != (args.header_output is None):
        parser.error("--source-output and --header-output must be used together")
    if args.check and args.source_output is not None:
        parser.error("--check cannot be used with explicit output paths")
    if not catalog_path.exists():
        parser.error("named behavior catalog is missing")
    catalog = authoring.json.loads(catalog_path.read_text())
    authoring.validate_behavior_catalog(catalog)
    current_source = source_template.read_text()
    current_header = header_template.read_text()
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

    if args.source_output is not None and args.header_output is not None:
        source_output = args.source_output.resolve()
        header_output = args.header_output.resolve()
        source_output.parent.mkdir(parents=True, exist_ok=True)
        header_output.parent.mkdir(parents=True, exist_ok=True)
        source_output.write_text(generated_source)
        header_output.write_text(generated_header)
        print(f"Generated {source_output} and {header_output}")
        return 0

    authoring.write_behavior_catalog(catalog)
    print(f"Generated {authoring.BEHAVIOR_DATA_SOURCE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
