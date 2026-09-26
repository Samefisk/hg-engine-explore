#!/usr/bin/env python3
"""Migrate one explicit behavior catalog path from authoring v4 to v5."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
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


def read_catalog(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
    except FileNotFoundError as error:
        raise ValueError(f"migration input does not exist: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(f"migration input is not valid JSON: {error}") from error
    if not isinstance(value, dict):
        raise ValueError("migration input must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate an explicit overworld behavior catalog from v4 to v5."
    )
    parser.add_argument("--input", type=Path, required=True, help="v4 or v5 input path")
    parser.add_argument("--output", type=Path, required=True, help="new v5 output path")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print deterministic v5 JSON without writing the output path",
    )
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve()
    if input_path == output_path:
        parser.error("--output must differ from --input; v4 input is read-only")
    if not args.dry_run and output_path.exists():
        parser.error(f"output already exists: {output_path}")

    authoring = load_authoring_module()
    try:
        migrated = authoring.migrate_behavior_catalog_v4_to_v5(
            read_catalog(input_path)
        )
    except (ValueError, authoring.ParseError) as error:
        print(f"Migration failed: {error}", file=sys.stderr)
        return 1

    rendered = json.dumps(migrated, indent=2, ensure_ascii=False) + "\n"
    if args.dry_run:
        sys.stdout.write(rendered)
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered)
    print(f"Migrated {input_path} to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
