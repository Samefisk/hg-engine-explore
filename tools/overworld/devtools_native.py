"""Private melonDS transport; no command line or gameplay test helpers.

Load by file path before adding the repository to sys.path. The exact isolated
startup and repository interpreter checks run before any native library import.
"""
import sys

def _isolated_helper_path():
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    base = sys.base_prefix + "/lib/" + version
    paths = (base, base + "/lib-dynload")
    if globals().get("AUTHENTICATED_MELONDS_LIBRARY") is None:
        venv = sys.executable.rsplit("/bin/", 1)[0]
        paths += (venv + "/lib/" + version + "/site-packages",)
    return paths


def _normalize_isolated_helper_path():
    expected = _isolated_helper_path()
    startup = (
        sys.base_prefix
        + "/lib/python"
        + str(sys.version_info.major)
        + str(sys.version_info.minor)
        + ".zip",
        expected[0],
        expected[1],
    )
    if (
        sys.flags.isolated == 1
        and sys.flags.ignore_environment == 1
        and sys.flags.no_site == 1
        and sys.dont_write_bytecode
        and sys.pycache_prefix == "/dev/null"
        and tuple(sys.path) == startup
    ):
        sys.path[:] = expected
        external = sys.modules["_frozen_importlib_external"]
        sys.path_hooks[:] = [
            external.FileFinder.path_hook(
                (external.SourceFileLoader, external.SOURCE_SUFFIXES),
                (external.ExtensionFileLoader, external.EXTENSION_SUFFIXES),
            )
        ]
        sys.path_importer_cache.clear()

_normalize_isolated_helper_path()


def _isolated_helper_startup():
    expected = _isolated_helper_path()
    return (
        sys.flags.isolated == 1
        and sys.flags.ignore_environment == 1
        and sys.flags.no_site == 1
        and sys.dont_write_bytecode
        and sys.pycache_prefix == "/dev/null"
        and "site" not in sys.modules
        and tuple(sys.path) == expected
    )

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DSV_FOOTER_MARKER = (
    b"|<--Snip above here to create a raw sav by excluding this DeSmuME savedata footer:"
)


def ensure_repo_venv() -> None:
    venv = REPO_ROOT / ".venv"
    venv_python = venv / "bin/python3"
    if (
        Path(os.path.abspath(sys.executable))
        != Path(os.path.abspath(venv_python))
        or not _isolated_helper_startup()
    ):
        raise RuntimeError(
            "headless helper requires exact repository Python with "
            "-I -S -B -X pycache_prefix=/dev/null"
        )

ensure_repo_venv()
ISOLATED_STARTUP_AUTHENTICATED = True

import ctypes
from contextlib import contextmanager

KEYS = {name: index + 1 for index, name in enumerate(
    ("A", "B", "SELECT", "START", "RIGHT", "LEFT", "UP", "DOWN", "R", "L", "X", "Y"))}


def keymask(key):
    return 1 << (key - 1)


def create_emulator():
    backend = globals().get("AUTHENTICATED_MELONDS_BACKEND")
    library = globals().get("AUTHENTICATED_MELONDS_LIBRARY")
    if backend is not None or library is not None:
        if backend is None or library is None:
            raise RuntimeError("incomplete authenticated melonDS transport")
        return backend.MelonDS(library=library)
    try:
        from tools.overworld.melonds_backend import MelonDS
    except ModuleNotFoundError as error:
        raise RuntimeError("melonDS shared bridge is not ready; DeSmuME fallback is disabled") from error
    return MelonDS()


def extract_raw_save(dsv_path: Path) -> bytes:
    data = dsv_path.read_bytes()
    marker_index = data.find(DSV_FOOTER_MARKER)
    if marker_index < 0:
        raise ValueError(
            f"{dsv_path} does not look like a DeSmuME .dsv with a savedata footer"
        )
    return data[:marker_index]


def cycle(emu, frames: int, key_mask: int | None = None) -> None:
    for _ in range(frames):
        if key_mask is not None:
            # Publish the full active-high pressed-key mask at the boundary.
            set_key_mask(emu, key_mask)
        emu.cycle(False)


def key_constant(name: str) -> int:
    normalized = name.strip().upper()
    if normalized not in KEYS:
        valid = ", ".join(sorted(KEYS))
        raise ValueError(f"Unknown key {name!r}. Valid keys: {valid}")
    return KEYS[normalized]


def set_key_mask(emu, key_mask: int) -> None:
    """Publish the complete pressed-key mask for the next emulated frame.

    The backend owns conversion to the active-low hardware register. Never
    combine a hardware readback with this active-high pressed-key mask.
    """
    emu.input.keypad_update(key_mask)


def tap_key(emu, key: str, hold_frames: int, release_frames: int) -> None:
    key_mask = keymask(key_constant(key))
    set_key_mask(emu, key_mask)
    cycle(emu, hold_frames, key_mask)
    set_key_mask(emu, 0)
    cycle(emu, release_frames)


def hold_key(emu, key: str, frames: int, release_frames: int) -> None:
    """Bounded input used by the separate Summary and party-integrity checks."""
    key_mask = keymask(key_constant(key))
    set_key_mask(emu, key_mask)
    cycle(emu, frames, key_mask)
    set_key_mask(emu, 0)
    cycle(emu, release_frames)


def boot_to_ready(args, emu) -> int:
    """Play a declared boot input sequence; the caller must prove readiness."""
    total_frames = 0
    cycle(emu, args.boot_frames)
    total_frames += args.boot_frames
    for _ in range(args.ready_a_taps):
        tap_key(emu, "A", args.tap_hold_frames, args.tap_gap_frames)
        total_frames += args.tap_hold_frames + args.tap_gap_frames
    cycle(emu, args.load_frames)
    total_frames += args.load_frames
    return total_frames


@contextmanager
def silence_native_output(enabled: bool):
    """Keep native chatter out of a caller-owned JSON result channel."""
    if not enabled:
        yield
        return
    sys.stdout.flush()
    sys.stderr.flush()
    old_stdout = os.dup(1)
    old_stderr = os.dup(2)
    with open(os.devnull, "wb") as devnull:
        os.dup2(devnull.fileno(), 1)
        os.dup2(devnull.fileno(), 2)
        try:
            yield
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            ctypes.CDLL(None).fflush(None)
            os.dup2(old_stdout, 1)
            os.dup2(old_stderr, 2)
            os.close(old_stdout)
            os.close(old_stderr)
