"""Private session copies: macOS copy-on-write, never shared writable files.

Only new destination paths are accepted. Closed sessions can remove their
verified private ROM copy; saves and evidence are never cleanup targets.
"""
from __future__ import annotations

import ctypes
import errno
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import sys


def _clone_file(source: Path, target: Path) -> bool:
    if sys.platform != "darwin":
        return False
    try:
        clonefile = ctypes.CDLL(None, use_errno=True).clonefile
    except AttributeError:
        return False  # Older macOS does not export clonefile.
    clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32]
    clonefile.restype = ctypes.c_int
    # sys/clonefile.h: CLONE_NOFOLLOW | CLONE_NOOWNERCOPY. The caller has
    # resolved the source, and owns the new private destination directory.
    if clonefile(os.fsencode(source), os.fsencode(target), 0x0001 | 0x0002) == 0:
        return True
    code = ctypes.get_errno() or errno.EIO
    if code in {errno.ENOTSUP, errno.EOPNOTSUPP, errno.ENOSYS, errno.EXDEV}:
        return False
    # In particular, do not retry a full allocation after ENOSPC or replace a
    # destination following EEXIST/permission errors.
    raise OSError(code, os.strerror(code), str(target))


def copy_private_file(source: Path, target: Path) -> str:
    """Copy into a distinct, writable inode and report the copy method."""
    source, target = Path(source), Path(target)
    if not stat.S_ISREG(source.stat().st_mode):
        raise ValueError("session source must be a regular file")
    if os.path.lexists(target):
        raise FileExistsError(errno.EEXIST, os.strerror(errno.EEXIST), str(target))
    cloned = _clone_file(source, target)
    if not cloned:
        with source.open("rb") as input_file, target.open("xb") as output_file:
            shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
    source_info, target_info = source.stat(), target.stat()
    if (source_info.st_dev, source_info.st_ino) == (target_info.st_dev, target_info.st_ino):
        raise ValueError("session copy must not share the source inode")
    # clonefile preserves source mode. The disposable copy must remain usable
    # even when the original save is deliberately read-only.
    target.chmod(stat.S_IMODE(target_info.st_mode) | stat.S_IRUSR | stat.S_IWUSR)
    return "clonefile" if cloned else "copy"


def remove_private_rom(session_directory: Path, rom_identity: dict) -> dict:
    """Remove one verified private game.nds. Caller must close the core first.

The session directory must be the canonical direct child of a repository's
build/overworld-devtools directory. No source existence/hash assumption is
made: another build may already have replaced that original ROM.
"""
    directory = Path(session_directory)
    if (not directory.is_absolute() or directory != directory.resolve()
            or not directory.is_dir()
            or directory.parent.name != "overworld-devtools"
            or directory.parent.parent.name != "build"
            or not re.fullmatch(r"session-[A-Za-z0-9_-]+", directory.name)):
        raise ValueError("ROM cleanup requires a canonical owned session directory")
    target = directory / "game.nds"
    if not isinstance(rom_identity, dict) or rom_identity.get("copy") != str(target):
        raise ValueError("ROM cleanup copy path differs")
    expected_hash, expected_size = rom_identity.get("sha256"), rom_identity.get("size")
    if (not isinstance(expected_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)
            or type(expected_size) is not int or expected_size <= 0):
        raise ValueError("ROM cleanup requires exact hash and size")
    source_value = rom_identity.get("path")
    if not isinstance(source_value, str) or not Path(source_value).is_absolute():
        raise ValueError("ROM cleanup source path is unknown")
    source = Path(source_value)
    if source.resolve() == target:
        raise ValueError("ROM cleanup target is the source")

    # Pin the directory and use no-follow operations for the one target name.
    parent_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        if (directory.stat().st_dev, directory.stat().st_ino) != (
                os.fstat(parent_fd).st_dev, os.fstat(parent_fd).st_ino):
            raise ValueError("ROM cleanup session directory changed")
        try:
            file_fd = os.open("game.nds", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
        except FileNotFoundError:
            return {"status": "absent", "sha256": expected_hash, "bytes": 0}
        with os.fdopen(file_fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                raise ValueError("ROM cleanup target must be a private regular file")
            try:
                original = source.stat()
            except FileNotFoundError:
                original = None
            if original and (before.st_dev, before.st_ino) == (original.st_dev, original.st_ino):
                raise ValueError("ROM cleanup target shares the source inode")
            if before.st_size != expected_size:
                raise ValueError("ROM cleanup size differs")
            hasher = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                hasher.update(chunk)
            if hasher.hexdigest() != expected_hash:
                raise ValueError("ROM cleanup hash differs")
            stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
            current = os.stat("game.nds", dir_fd=parent_fd, follow_symlinks=False)
            if stamp(before) != stamp(os.fstat(stream.fileno())) or stamp(before) != stamp(current):
                raise ValueError("ROM cleanup target changed during verification")
            os.unlink("game.nds", dir_fd=parent_fd)
        return {"status": "removed", "sha256": expected_hash, "bytes": expected_size}
    finally:
        os.close(parent_fd)
