#!/usr/bin/env python3
"""Generate the compact OWBD v40 member from its canonical authored JSON."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

from overworld_wild_behavior_model_v40 import (
    CHECKSUM_OFFSET,
    DEFAULT_HEADER,
    DEFAULT_MODEL,
    DEFAULT_OUTPUT,
    encode_model,
    load_model,
    render_header,
    render_inc,
    section_counts,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--header", type=Path, default=DEFAULT_HEADER)
    parser.add_argument("--raw-output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    model = load_model(args.model)
    blob = encode_model(model)
    rendered_inc = render_inc(blob)
    rendered_header = render_header(model, blob, args.header.read_text())
    if args.check:
        stale = []
        if not args.output.exists() or args.output.read_text() != rendered_inc:
            stale.append(str(args.output))
        if args.header.read_text() != rendered_header:
            stale.append(str(args.header))
        if stale:
            raise SystemExit("stale generated file(s): " + ", ".join(stale))
    else:
        args.output.write_text(rendered_inc)
        args.header.write_text(rendered_header)
    if args.raw_output:
        args.raw_output.write_bytes(blob)

    checksum = struct.unpack_from("<I", blob, CHECKSUM_OFFSET)[0]
    print(
        f"OWBD v40 canonical model: size={len(blob)} checksum=0x{checksum:08X} "
        f"fingerprint=0x{model['wire']['schemaFingerprint']:08X}"
    )
    print("counts=" + ",".join(
        f"{name}:{count}" for name, count in section_counts(model).items()
    ))


if __name__ == "__main__":
    main()
