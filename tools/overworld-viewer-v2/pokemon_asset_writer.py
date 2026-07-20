"""Validated staging and binary-safe replacement of source Pokémon PNG assets."""

from __future__ import annotations

import ast
import hashlib
import os
import re
import struct
import stat as stat_module
import tempfile
import threading
import time
import uuid
import zlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pokemon_writer


MANIFEST_RELATIVE = "data/graphics/pokegra.mk"
SPECIES_RELATIVE = "asm/include/species.inc"
MAX_ASSET_BYTES = 2 * 1024 * 1024
STAGING_TTL_SECONDS = 30 * 60
SLOT_RULES = {
    "icon": ("icon", 32, 64),
    "follower": ("follower", 32, 256),
    "maleFront": ("male-front", 160, 80),
    "femaleFront": ("female-front", 160, 80),
    "maleBack": ("male-back", 160, 80),
    "femaleBack": ("female-back", 160, 80),
}
FOLLOWER_TABLE_RELATIVE = "src/field/overworld_table.c"


@dataclass(frozen=True)
class StagedAsset:
    token: str
    symbol: str
    slot: str
    destination: Path
    temporary: Path
    digest: str
    width: int
    height: int
    size: int
    source_revision: str
    asset_revision: str
    expires_at: float


STAGING_LOCK = threading.Lock()
STAGED: dict[str, StagedAsset] = {}
UNCHECKED_IDENTITY = object()


def _secure_staging_root() -> Path:
    staging_root = Path(tempfile.gettempdir()) / "overworld-viewer-v2-pokemon-assets"
    try:
        staging_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = staging_root.lstat()
    except OSError as exc:
        raise ValueError("asset staging directory is unavailable") from exc
    if stat_module.S_ISLNK(info.st_mode) or not stat_module.S_ISDIR(info.st_mode):
        raise ValueError("asset staging path must be a real directory")
    if info.st_uid != os.getuid():
        raise ValueError("asset staging directory is owned by another user")
    if info.st_mode & 0o077:
        os.chmod(staging_root, 0o700)
        info = staging_root.lstat()
        if info.st_mode & 0o077:
            raise ValueError("asset staging directory permissions are unsafe")
    return staging_root


def _contained(root: Path, candidate: Path, *, must_exist: bool) -> Path:
    root = root.resolve(strict=True)
    lexical = candidate if candidate.is_absolute() else root / candidate
    try:
        lexical.absolute().relative_to(root)
    except ValueError as exc:
        raise ValueError("asset destination escapes the repository") from exc
    cursor = lexical
    while cursor != root:
        if cursor.is_symlink():
            raise ValueError("symlinked asset paths are not writable")
        if not cursor.exists():
            cursor = cursor.parent
            continue
        cursor = cursor.parent
    try:
        resolved = lexical.resolve(strict=must_exist)
        resolved.relative_to(root)
    except (FileNotFoundError, ValueError) as exc:
        raise ValueError("asset destination escapes the repository") from exc
    if must_exist and not resolved.is_file():
        raise ValueError("asset destination is not a regular file")
    return resolved


@lru_cache(maxsize=8)
def _species_values_cached(
    root_value: str, content_digest: str, source_bytes: bytes
) -> dict[str, int]:
    del root_value, content_digest
    text = source_bytes.decode("utf-8")
    values: dict[str, int] = {}

    def evaluate(node: ast.AST) -> int:
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.Name) and node.id in values:
            return values[node.id]
        if isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.LShift, ast.RShift, ast.BitOr)
        ):
            left, right = evaluate(node.left), evaluate(node.right)
            return {
                ast.Add: lambda: left + right,
                ast.Sub: lambda: left - right,
                ast.Mult: lambda: left * right,
                ast.FloorDiv: lambda: left // right,
                ast.LShift: lambda: left << right,
                ast.RShift: lambda: left >> right,
                ast.BitOr: lambda: left | right,
            }[type(node.op)]()
        raise ValueError("unsupported species constant expression")

    for symbol, expression in re.findall(
        r"(?m)^\s*\.equ\s+([A-Z][A-Z0-9_]+)\s*,\s*([^/\r\n]+)", text
    ):
        try:
            values[symbol] = evaluate(ast.parse(expression.strip(), mode="eval"))
        except (SyntaxError, ValueError, ZeroDivisionError):
            continue
    return {symbol: value for symbol, value in values.items() if symbol.startswith("SPECIES_")}


def _species_values(root: Path) -> dict[str, int]:
    body = (root / SPECIES_RELATIVE).read_bytes()
    return _species_values_cached(str(root), hashlib.sha256(body).hexdigest(), body)


def species_values(root: Path) -> dict[str, int]:
    """Return evaluated species constants for asset-manifest joins."""

    return _species_values(Path(root).resolve())


@lru_cache(maxsize=8)
def _follower_manifest_cached(
    root_value: str, content_digest: str, source_bytes: bytes
) -> dict[str, Path]:
    del content_digest
    root = Path(root_value)
    result: dict[str, Path] = {}
    pattern = re.compile(
        r"\{\s*\.tag\s*=\s*\d+\s*,\s*\.gfx\s*=\s*(\d+).*?//\s*(SPECIES_[A-Z0-9_]+)\b"
    )
    for raw_line in source_bytes.decode("utf-8").splitlines():
        match = pattern.search(raw_line)
        if match:
            result.setdefault(
                match.group(2),
                _contained(
                    root,
                    root / "data/graphics/overworlds" / f"{int(match.group(1)):04d}.png",
                    must_exist=False,
                ),
            )
    return result


def follower_manifest(root: Path) -> dict[str, Path]:
    """Resolve canonical Pokémon symbols to their field follower sprite sheet."""

    root = Path(root).resolve()
    body = (root / FOLLOWER_TABLE_RELATIVE).read_bytes()
    return _follower_manifest_cached(str(root), hashlib.sha256(body).hexdigest(), body)


@lru_cache(maxsize=8)
def _manifest_cached(
    root_value: str, content_digest: str, source_bytes: bytes
) -> dict[tuple[int, str], Path]:
    del content_digest
    root = Path(root_value)
    text = source_bytes.decode("utf-8")
    result: dict[tuple[int, str], Path] = {}
    for line in text.splitlines():
        icon = re.search(r"build/pokemonicon/1_(\d+)\.NCGR:\s+([^\s]+/icon\.png)", line)
        if icon:
            result[(int(icon.group(1)), "icon")] = _contained(root, Path(icon.group(2)), must_exist=False)
            continue
        sprite = re.search(r"build/pokemonpic/(\d+)-([0-3][0-9])\.NCGR:\s+([^\s]+\.png)", line)
        kind = {"00": "female-back", "01": "male-back", "02": "female-front", "03": "male-front"}.get(sprite.group(2)) if sprite else None
        if sprite and kind:
            result[(int(sprite.group(1)), kind)] = _contained(root, Path(sprite.group(3)), must_exist=False)
    return result


def _manifest(root: Path) -> dict[tuple[int, str], Path]:
    body = (root / MANIFEST_RELATIVE).read_bytes()
    return _manifest_cached(str(root), hashlib.sha256(body).hexdigest(), body)


def _destination_from_maps(
    root: Path,
    symbol: str,
    slot: str,
    values: dict[str, int],
    manifest: dict[tuple[int, str], Path],
) -> Path:
    canonical = pokemon_writer.canonical_species_symbol(symbol)
    if canonical not in values:
        raise ValueError(f"unknown asset species {symbol}")
    rule = SLOT_RULES.get(slot)
    if rule is None:
        raise ValueError(f"unknown asset slot {slot}")
    destination = (
        follower_manifest(root).get(canonical)
        if slot == "follower"
        else manifest.get((values[canonical], rule[0]))
    )
    if destination is None:
        raise ValueError(f"{canonical}.{slot} has no source PNG declared by the generated manifest")
    return _contained(root, destination, must_exist=False)


def _destination(root: Path, symbol: str, slot: str) -> Path:
    return _destination_from_maps(root, symbol, slot, _species_values(root), _manifest(root))


def _png_info(body: bytes, slot: str) -> tuple[int, int]:
    if len(body) > MAX_ASSET_BYTES:
        raise ValueError(f"asset exceeds {MAX_ASSET_BYTES} bytes")
    if len(body) < 33 or body[:8] != b"\x89PNG\r\n\x1a\n" or body[12:16] != b"IHDR":
        raise ValueError("asset must be a valid PNG image")
    _, expected_width, expected_height = SLOT_RULES[slot]
    cursor = 8
    chunk_types: list[bytes] = []
    seen_critical: set[bytes] = set()
    idat_bytes = 0
    idat_ended = False
    color_type: int | None = None
    bit_depth: int | None = None
    idat_parts: list[bytes] = []
    while cursor < len(body):
        if cursor + 12 > len(body):
            raise ValueError("PNG contains a truncated chunk")
        length = struct.unpack(">I", body[cursor:cursor + 4])[0]
        chunk_type = body[cursor + 4:cursor + 8]
        end = cursor + 12 + length
        if end > len(body):
            raise ValueError("PNG contains a truncated chunk payload")
        chunk_data = body[cursor + 8:cursor + 8 + length]
        expected_crc = struct.unpack(">I", body[cursor + 8 + length:end])[0]
        if zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF != expected_crc:
            raise ValueError("PNG chunk integrity validation failed")
        if not chunk_types and (chunk_type != b"IHDR" or length != 13):
            raise ValueError("PNG must begin with one 13-byte IHDR chunk")
        critical = 65 <= chunk_type[0] <= 90
        if critical:
            if chunk_type not in {b"IHDR", b"PLTE", b"IDAT", b"IEND"}:
                raise ValueError("PNG contains an unknown critical chunk")
            if chunk_type in seen_critical and chunk_type != b"IDAT":
                raise ValueError("PNG contains a duplicate critical chunk")
            seen_critical.add(chunk_type)
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", chunk_data
            )
            if width == 0 or height == 0 or (width, height) != (
                expected_width,
                expected_height,
            ):
                raise ValueError(
                    f"{slot} must be exactly {expected_width}x{expected_height} pixels"
                )
            legal_depths = {
                0: {1, 2, 4, 8, 16},
                2: {8, 16},
                3: {1, 2, 4, 8},
                4: {8, 16},
                6: {8, 16},
            }
            if color_type not in legal_depths or bit_depth not in legal_depths[color_type]:
                raise ValueError("PNG uses an illegal bit-depth/color-type pair")
            if compression != 0 or filtering != 0 or interlace not in {0, 1}:
                raise ValueError("PNG uses unsupported compression, filter, or interlace methods")
            if interlace != 0:
                raise ValueError("interlaced PNG assets are not supported")
        elif chunk_type == b"PLTE":
            if (
                b"IDAT" in seen_critical
                or color_type in {0, 4}
                or not length
                or length % 3
                or length > 768
                or (color_type == 3 and bit_depth is not None and length // 3 > 2**bit_depth)
            ):
                raise ValueError("PNG contains an invalid or misplaced PLTE chunk")
        elif chunk_type == b"IDAT":
            if idat_ended or length == 0:
                raise ValueError("PNG IDAT chunks must be nonempty and consecutive")
            idat_bytes += length
            idat_parts.append(chunk_data)
        elif b"IDAT" in seen_critical and chunk_type != b"IEND":
            idat_ended = True
        if chunk_type == b"IEND" and length != 0:
            raise ValueError("PNG IEND must be zero-length")
        chunk_types.append(chunk_type)
        cursor = end
        if chunk_type == b"IEND":
            break
    if (
        not chunk_types
        or chunk_types.count(b"IHDR") != 1
        or chunk_types[-1] != b"IEND"
        or cursor != len(body)
        or idat_bytes == 0
        or (color_type == 3 and b"PLTE" not in chunk_types)
    ):
        raise ValueError("PNG is missing canonical IHDR/IEND structure")
    width, height = struct.unpack(">II", body[16:24])
    assert color_type is not None and bit_depth is not None
    try:
        channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
        row_bytes = (width * channels * bit_depth + 7) // 8
        expected_decoded = height * (1 + row_bytes)
        compressed = b"".join(idat_parts)
        inflater = zlib.decompressobj()
        decoded = inflater.decompress(compressed, expected_decoded + 1)
        if len(decoded) <= expected_decoded:
            decoded += inflater.flush(expected_decoded + 1 - len(decoded))
    except (zlib.error, OverflowError, MemoryError, ValueError) as exc:
        raise ValueError("PNG IDAT cannot be safely decoded") from exc
    if (
        len(decoded) != expected_decoded
        or not inflater.eof
        or inflater.unconsumed_tail
        or inflater.unused_data
    ):
        raise ValueError("PNG decoded scanline size or zlib stream boundary is invalid")
    stride = row_bytes + 1
    if any(decoded[offset] not in range(5) for offset in range(0, len(decoded), stride)):
        raise ValueError("PNG scanline uses an invalid filter byte")
    return width, height


def _open_parent_fd(root: Path, destination: Path) -> tuple[int, str]:
    root = root.resolve(strict=True)
    try:
        relative = destination.absolute().relative_to(root)
    except ValueError as exc:
        raise ValueError("asset destination escapes the repository") from exc
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError("asset destination has an invalid relative path")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(root, flags)
    try:
        for part in relative.parts[:-1]:
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor, relative.parts[-1]
    except Exception:
        os.close(descriptor)
        raise


def read_asset_source(
    root: Path, destination: Path
) -> tuple[bytes | None, int | None, tuple[int, int, int, int, int, str] | None]:
    parent_fd, name = _open_parent_fd(Path(root), destination)
    try:
        try:
            descriptor = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
        except FileNotFoundError:
            return None, None, None
        try:
            info = os.fstat(descriptor)
            if not stat_module.S_ISREG(info.st_mode):
                raise ValueError("asset source is not a regular file")
            chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            body = b"".join(chunks)
            after = os.fstat(descriptor)
            identity = (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
                hashlib.sha256(body).hexdigest(),
            )
            if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns) != identity[:5]:
                raise ValueError("asset source changed while being snapshotted")
            return body, info.st_mode & 0o7777, identity
        finally:
            os.close(descriptor)
    finally:
        os.close(parent_fd)


def replace_asset_source(
    root: Path,
    destination: Path,
    body: bytes | None,
    *,
    mode: int | None = None,
    expected_identity: tuple[int, int, int, int, int, str] | None | object = UNCHECKED_IDENTITY,
) -> None:
    parent_fd, name = _open_parent_fd(Path(root), destination)
    temporary_name = f".{name}.v2-{uuid.uuid4().hex}.tmp"
    temporary_created = False
    try:
        try:
            current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if not stat_module.S_ISREG(current.st_mode):
                raise ValueError("asset destination is not a regular file")
            descriptor = os.open(
                name,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=parent_fd,
            )
            try:
                current_body = b""
                while True:
                    chunk = os.read(descriptor, 1024 * 1024)
                    if not chunk:
                        break
                    current_body += chunk
                current_after = os.fstat(descriptor)
            finally:
                os.close(descriptor)
            if (
                current.st_dev,
                current.st_ino,
                current.st_size,
                current.st_mtime_ns,
                current.st_ctime_ns,
            ) != (
                current_after.st_dev,
                current_after.st_ino,
                current_after.st_size,
                current_after.st_mtime_ns,
                current_after.st_ctime_ns,
            ):
                raise ValueError("asset destination changed during identity verification")
            current_identity: tuple[int, int, int, int, int, str] | None = (
                current_after.st_dev,
                current_after.st_ino,
                current_after.st_size,
                current_after.st_mtime_ns,
                current_after.st_ctime_ns,
                hashlib.sha256(current_body).hexdigest(),
            )
        except FileNotFoundError:
            current_identity = None
        if expected_identity is not UNCHECKED_IDENTITY and current_identity != expected_identity:
            raise ValueError("asset destination changed during the transaction")
        if body is None:
            if current_identity is not None:
                os.unlink(name, dir_fd=parent_fd)
                os.fsync(parent_fd)
            return
        descriptor = os.open(
            temporary_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            mode if mode is not None else 0o644,
            dir_fd=parent_fd,
        )
        temporary_created = True
        try:
            view = memoryview(body)
            while view:
                written = os.write(descriptor, view)
                view = view[written:]
            os.fsync(descriptor)
            os.fchmod(descriptor, mode if mode is not None else 0o644)
        finally:
            os.close(descriptor)
        latest_identity = None
        try:
            latest = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            latest_identity = (
                latest.st_dev,
                latest.st_ino,
                latest.st_size,
                latest.st_mtime_ns,
                latest.st_ctime_ns,
                current_identity[5] if current_identity else "",
            )
        except FileNotFoundError:
            pass
        if latest_identity != current_identity:
            raise ValueError("asset destination changed before atomic replacement")
        os.replace(
            temporary_name,
            name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )
        temporary_created = False
        os.fsync(parent_fd)
    finally:
        if temporary_created:
            try:
                os.unlink(temporary_name, dir_fd=parent_fd)
            except FileNotFoundError:
                pass
        os.close(parent_fd)


def stage_asset(
    root: Path,
    symbol: str,
    slot: str,
    body: bytes,
    *,
    source_revision: str,
    asset_revision: str,
) -> dict[str, Any]:
    root = Path(root).resolve()
    canonical = pokemon_writer.canonical_species_symbol(symbol)
    destination = _destination(root, canonical, slot)
    width, height = _png_info(body, slot)
    token = uuid.uuid4().hex
    staging_root = _secure_staging_root()
    temporary = staging_root / f"{token}.png"
    staging_fd = os.open(
        staging_root,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        descriptor = os.open(
            temporary.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=staging_fd,
        )
        with os.fdopen(descriptor, "wb") as output:
            output.write(body)
            output.flush()
            os.fsync(output.fileno())
    finally:
        os.close(staging_fd)
    expires_at = time.time() + STAGING_TTL_SECONDS
    staged = StagedAsset(token, canonical, slot, destination, temporary, hashlib.sha256(body).hexdigest(), width, height, len(body), source_revision, asset_revision, expires_at)
    with STAGING_LOCK:
        _purge_expired_locked()
        STAGED[token] = staged
    return {
        "stagingToken": token,
        "previewUrl": f"/api/v2/pokemon-assets/staged/{token}",
        "mimeType": "image/png",
        "width": width,
        "height": height,
        "bytes": len(body),
        "sourceRevision": source_revision,
        "assetRevision": asset_revision,
        "expiresAt": expires_at,
    }


def _purge_expired_locked() -> None:
    now = time.time()
    for token, staged in list(STAGED.items()):
        if staged.expires_at <= now:
            try:
                staged.temporary.unlink(missing_ok=True)
            except OSError:
                pass
            STAGED.pop(token, None)
    try:
        staging_root = _secure_staging_root()
    except ValueError:
        return
    if staging_root.is_dir() and not staging_root.is_symlink():
        live_paths = {staged.temporary for staged in STAGED.values()}
        for candidate in staging_root.glob("*.png"):
            try:
                stat = candidate.lstat()
                if (
                    candidate not in live_paths
                    and not candidate.is_symlink()
                    and now - stat.st_mtime >= STAGING_TTL_SECONDS
                ):
                    candidate.unlink(missing_ok=True)
            except OSError:
                pass


def staged_body(token: str) -> bytes | None:
    preview = staged_preview(token)
    return preview[0] if preview else None


def staged_preview(token: str) -> tuple[bytes, str, str] | None:
    """Return validated staged bytes plus the identity needed to render previews."""

    if not re.fullmatch(r"[0-9a-f]{32}", token):
        return None
    try:
        _secure_staging_root()
    except ValueError:
        return None
    with STAGING_LOCK:
        _purge_expired_locked()
        staged = STAGED.get(token)
        if staged is None:
            return None
        try:
            descriptor = os.open(
                staged.temporary, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            )
            with os.fdopen(descriptor, "rb") as source:
                if not stat_module.S_ISREG(os.fstat(source.fileno()).st_mode):
                    return None
                body = source.read()
        except (FileNotFoundError, OSError):
            return None
        if hashlib.sha256(body).hexdigest() != staged.digest:
            return None
        return body, staged.symbol, staged.slot


def discard_token(token: str) -> bool:
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        return False
    try:
        _secure_staging_root()
    except ValueError:
        return False
    with STAGING_LOCK:
        _purge_expired_locked()
        staged = STAGED.pop(token, None)
        if staged is None:
            return False
        try:
            staged.temporary.unlink(missing_ok=True)
        except OSError:
            pass
        return True


def mutation_paths_for_payload(root: Path, payload: Any) -> tuple[Path, ...]:
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        return ()
    paths: set[Path] = set()
    with STAGING_LOCK:
        _purge_expired_locked()
        for record in payload["records"]:
            if not isinstance(record, dict) or not isinstance(record.get("assets"), dict):
                continue
            for value in record["assets"].values():
                if isinstance(value, dict) and isinstance(value.get("stagingToken"), str):
                    staged = STAGED.get(value["stagingToken"])
                    if staged:
                        paths.add(staged.destination)
    return tuple(sorted(paths))


def asset_access(
    root: Path,
    symbol: str,
    *,
    values: dict[str, int] | None = None,
    manifest: dict[tuple[int, str], Path] | None = None,
) -> dict[str, Any]:
    root = Path(root).resolve()
    values = values if values is not None else _species_values(root)
    manifest = manifest if manifest is not None else _manifest(root)
    slots: dict[str, Any] = {}
    for slot, (_, width, height) in SLOT_RULES.items():
        try:
            path = _destination_from_maps(root, symbol, slot, values, manifest)
            writable, reason = True, None
            status = "available" if path.is_file() else "missing"
            size = path.stat().st_size if path.is_file() else None
            generated = False
            provenance = "source-png"
            diagnostics: list[str] = []
            if path.is_file() and size == 0:
                status = "generated-fallback"
                generated = True
                provenance = "empty-source-placeholder"
                diagnostics.append(
                    "empty source placeholder currently uses the engine's gender fallback; staging a PNG makes this slot explicit"
                )
            elif path.is_file():
                try:
                    _png_info(path.read_bytes(), slot)
                except ValueError as exc:
                    status = "invalid-source"
                    diagnostics.append(str(exc))
        except ValueError as exc:
            path, writable, reason, status, size = None, False, str(exc), "unavailable", None
            generated, provenance, diagnostics = True, "generated-manifest", [str(exc)]
        slots[slot] = {
            "label": {
                "icon": "Menu icon",
                "follower": "Overworld follower",
            }.get(slot, slot.replace("Front", " front").replace("Back", " back").title()),
            "mimeType": "image/png",
            "width": width,
            "height": height,
            "bytes": size,
            "status": status,
            "provenance": provenance,
            "generated": generated,
            "diagnostics": diagnostics,
            "source": path.relative_to(root).as_posix() if path else MANIFEST_RELATIVE,
            "access": {"writable": writable, "reason": reason},
        }
    writable = any(value["access"]["writable"] for value in slots.values())
    return {"writable": writable, "reason": None if writable else "no source PNG slots are writable", "slots": slots}


def asset_access_matrix(root: Path, symbols: list[str]) -> dict[str, dict[str, Any]]:
    root = Path(root).resolve()
    values = _species_values(root)
    manifest = _manifest(root)
    return {
        symbol: asset_access(root, symbol, values=values, manifest=manifest)
        for symbol in symbols
    }


def apply_asset_updates(root: Path, payload: Any, *, source_revision: str, asset_revision: str) -> dict[str, Any]:
    root = Path(root).resolve()
    _secure_staging_root()
    if not isinstance(payload, dict) or set(payload) != {"records"}:
        raise ValueError("asset update payload must contain exactly records")
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("asset update records must be a non-empty array")
    writes: list[
        tuple[
            StagedAsset,
            bytes,
            int | None,
            tuple[int, int, int, int, int, str] | None,
        ]
    ] = []
    unchanged_tokens: list[str] = []
    seen: set[tuple[str, str]] = set()
    with STAGING_LOCK:
        _purge_expired_locked()
        for index, record in enumerate(records):
            if not isinstance(record, dict) or set(record) != {"symbol", "assets"}:
                raise ValueError(f"records[{index}] must contain exactly symbol and assets")
            symbol = pokemon_writer.canonical_species_symbol(record["symbol"]) if isinstance(record.get("symbol"), str) else ""
            assets = record.get("assets")
            if not isinstance(assets, dict) or not assets:
                raise ValueError(f"{symbol}.assets must be a non-empty object")
            for slot, value in assets.items():
                if slot not in SLOT_RULES or not isinstance(value, dict) or set(value) != {"stagingToken"}:
                    raise ValueError(f"invalid staged asset shape for {symbol}.{slot}")
                token = value["stagingToken"]
                if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{32}", token):
                    raise ValueError(f"invalid staging token for {symbol}.{slot}")
                staged = STAGED.get(token)
                if staged is None:
                    raise ValueError(f"staging token for {symbol}.{slot} is missing or expired")
                if (symbol, slot) in seen:
                    raise ValueError(f"duplicate asset update for {symbol}.{slot}")
                seen.add((symbol, slot))
                if staged.symbol != symbol or staged.slot != slot:
                    raise ValueError("staging token does not match its species and slot")
                if staged.source_revision != source_revision or staged.asset_revision != asset_revision:
                    raise ValueError("staged asset was created for a stale source or asset revision")
                destination = _destination(root, symbol, slot)
                if destination != staged.destination:
                    raise ValueError("asset destination changed after staging")
                try:
                    descriptor = os.open(
                        staged.temporary,
                        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                    )
                    with os.fdopen(descriptor, "rb") as source:
                        if not stat_module.S_ISREG(os.fstat(source.fileno()).st_mode):
                            raise ValueError("staged asset is not a regular file")
                        body = source.read()
                except OSError as exc:
                    raise ValueError("staged asset content is unavailable") from exc
                _png_info(body, slot)
                if hashlib.sha256(body).hexdigest() != staged.digest:
                    raise ValueError("staged asset content failed integrity validation")
                current_body, current_mode, current_identity = read_asset_source(root, destination)
                if current_body == body:
                    unchanged_tokens.append(staged.token)
                    continue
                writes.append((staged, body, current_mode, current_identity))
    for staged, body, current_mode, current_identity in writes:
        replace_asset_source(
            root,
            staged.destination,
            body,
            mode=current_mode,
            expected_identity=current_identity,
        )
        verified_body, _, _ = read_asset_source(root, staged.destination)
        if verified_body is None:
            raise ValueError("asset destination disappeared after replacement")
        _png_info(verified_body, staged.slot)
        if hashlib.sha256(verified_body).hexdigest() != staged.digest:
            raise ValueError("asset destination failed post-commit integrity validation")
    changed_symbols = {staged.symbol for staged, _, _, _ in writes}
    changed_tokens = [staged.token for staged, _, _, _ in writes]
    consumed_tokens = changed_tokens + (unchanged_tokens if writes else [])
    retained_tokens = [] if writes else unchanged_tokens
    return {
        "saved": bool(writes),
        "changedRecords": len(changed_symbols),
        "changedAssets": len(writes),
        "unchangedAssets": len(unchanged_tokens),
        "sourceFiles": [staged.destination.relative_to(root).as_posix() for staged, _, _, _ in writes],
        "stagingTokens": consumed_tokens,
        "retainedStagingTokens": retained_tokens,
        "message": (
            "staged asset is identical; token retained"
            if not writes and unchanged_tokens
            else "asset sources replaced"
        ),
    }


def finalize_tokens(tokens: list[str]) -> None:
    with STAGING_LOCK:
        for token in tokens:
            staged = STAGED.pop(token, None)
            if staged:
                try:
                    staged.temporary.unlink(missing_ok=True)
                except OSError:
                    pass
