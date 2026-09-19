"""Lossless checked-job JSONL storage. Compression does not change evidence."""
from contextlib import contextmanager
import gzip
import io
import json
from pathlib import Path
import zlib

MAX_LINE_BYTES = 8 * 1024 * 1024
MAX_ROWS = 200000


def _compressed(path):
    name = Path(path).name
    if name.endswith(".jsonl.gz"):
        return True
    if name.endswith(".jsonl"):
        return False
    raise ValueError("observation path must end in .jsonl or .jsonl.gz")


@contextmanager
def open_observations(path, mode="rt"):
    """Open one text stream; append creates a standard concatenated gzip member."""
    if mode not in ("rt", "xt", "at"):
        raise ValueError("observation mode must be rt, xt or at")
    compressed = _compressed(path)
    if compressed:
        stream = gzip.open(path, mode, compresslevel=1, encoding="utf-8", errors="strict", newline="")
    else:
        stream = Path(path).open(mode, encoding="utf-8", errors="strict", newline="")
    try:
        yield stream
    finally:
        stream.close()


def load_observations(path):
    """Read bounded UTF-8 lines and require a valid compressed EOF, including CRC."""
    compressed = _compressed(path)
    rows = []
    try:
        with Path(path).open("rb") as raw:
            if compressed:
                if raw.read(2) != b"\x1f\x8b":
                    raise ValueError("invalid observation stream: missing gzip header")
                raw.seek(0)
            with (gzip.GzipFile(fileobj=raw, mode="rb") if compressed else io.BufferedReader(raw)) as stream:
                while True:
                    line = stream.readline(MAX_LINE_BYTES + 1)
                    if not line:
                        break
                    if len(line) > MAX_LINE_BYTES:
                        raise ValueError("observation line exceeds 8 MiB UTF-8 byte limit")
                    if len(rows) >= MAX_ROWS:
                        raise ValueError("observation row count exceeds 200000")
                    value = json.loads(line.decode("utf-8"), parse_constant=_invalid_constant)
                    if not isinstance(value, dict):
                        raise ValueError("observation row must be a JSON object")
                    rows.append(value)
    except (UnicodeError, json.JSONDecodeError, gzip.BadGzipFile, EOFError, zlib.error, RecursionError) as error:
        raise ValueError("invalid observation stream: " + str(error)) from error
    return rows


def _invalid_constant(value):
    raise ValueError("invalid observation JSON constant: " + value)
