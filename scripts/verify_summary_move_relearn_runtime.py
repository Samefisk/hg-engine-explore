#!/usr/bin/env python3
"""Deterministic key/touch Summary relearn acceptance on a preserved DSV."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path
from types import SimpleNamespace


REPO = Path(__file__).resolve().parents[1]
SAVE_DATA_POINTER = 0x021D2228
SAVE_HISTORY_POINTER_OFFSET = 0x2F30C
SAVE_HISTORY_METADATA_SIZE = 0x14
HISTORY_IMAGE_SIZE = 0x5000
HISTORY_HEADER_SIZE = 0x20
HISTORY_RECORD_SIZE = 0x40
HISTORY_RECORD_COUNT = 319
PARTY_OFFSET = 0xA0
PARTY_SIZE = 8 + 6 * 0xEC
LOCAL_FIELD_DATA_OFFSET = 0x1424
VARS_FLAGS_SAVE_OFFSET = 0x0FD4
DAYCARE_SAVE_OFFSET = 0x1BAC
DAYCARE_MON_SIZE = 0xEC
SAVED_MAP_OBJECTS_OFFSET = 0x2CC0
SAVED_MAP_OBJECT_SIZE = 0x50
PC_SAVE_OFFSET = 0x10000
PC_SAVE_SIZE = 0x1E4FC
PC_BOX_COUNT = 30
PC_BOX_SIZE = 0x1000
PC_MON_SIZE = 0x88
PC_MONS_PER_BOX = 30
PC_STORAGE_BOXES_SIZE = PC_BOX_COUNT * PC_BOX_SIZE
PC_FOOTER_SIZE = 0x10
PC_SAVE_SLOT = 1
SAVE_DYNAMIC_REGION_OFFSET = 0x10
PC_ACTIVE_BOX_OFFSET = PC_STORAGE_BOXES_SIZE
PC_MODIFIED_FLAGS_OFFSET = PC_STORAGE_BOXES_SIZE + 4
BOX_TARGET_SLOT = 0
BOX_SWITCH_SLOT = 1
BOX_TARGET_OT_ID_XOR = 0x13579BDF
BOX_SWITCH_OT_ID_XOR = 0x2468ACE0
TARGET_SLOT = 2
TARGET_SPECIES = 72
TARGET_REPLACEMENT_SLOT = 3
TARGET_MOVE = 40  # Poison Sting
CONTROLLED_MOVES = (57, 48, 352, 103)
CONTROLLED_PP = (8, 8, 8, 1)
CONTROLLED_PP_UPS = (0, 0, 0, 2)
CONTROLLED_HISTORY_MOVES = (
    57, 48, 352, 103, 62, 114, 229, 243
)
CONTROLLED_CANDIDATES = (40, 55, 51, 35, 62, 114, 229, 243)
PERSISTED_CANDIDATES = (55, 51, 35, 103, 62, 114, 229, 243)
HISTORY_MIRROR_OFFSETS = (0x3B000, 0x7B000)
HISTORY_FOOTER_OFFSET = 0x4FE0
HISTORY_FOOTER_MAGIC = 0x4D48464F
TASK6_POKEWALKER_STAGE_ENTRY = 0x023BD420
TASK6_POKEWALKER_ACK_FIRST_ENTRY = 0x023BD480
TASK6_POKEWALKER_ACK_SECOND_ENTRY = 0x023BD488
TASK6_POKEWALKER_RECOVERY_ENTRY = 0x023BD490
TASK6_POKEWALKER_DIAGNOSTIC_POLL = 0x023BD4A0
TASK6_POKEWALKER_MAILBOX = 0x023BD4A8
TASK6_POKEWALKER_MAILBOX_SIZE = 0x30
TASK6_POKEWALKER_MAILBOX_MAGIC = 0x36574B50
TASK6_POKEWALKER_MAILBOX_VERSION = 1
TASK6_POKEWALKER_STATUS_COMPLETE = 0xC0016D48
TASK6_POKEWALKER_OP_STAGE = 1
TASK6_POKEWALKER_OP_ACK_FIRST = 2
TASK6_POKEWALKER_OP_ACK_SECOND = 3
TASK6_POKEWALKER_OP_RECOVER = 4
SUMMARY_STATE_ORIGINAL_MOVES_OFFSET = 134
SUMMARY_STATE_CANDIDATE_COUNT_OFFSET = 150
SUMMARY_STATE_CANDIDATE_CURSOR_OFFSET = 152
SUMMARY_STATE_CANDIDATE_TOP_OFFSET = 154
SUMMARY_STATE_PENDING_MOVE_OFFSET = 156
SUMMARY_STATE_ORIGINAL_ARG_MOVE_OFFSET = 158
SUMMARY_STATE_OWNER_POS_OFFSET = 160
SUMMARY_STATE_SELECTED_SLOT_OFFSET = 161
SUMMARY_STATE_MODE_OFFSET = 163
SUMMARY_STATE_PROMPT_VISIBLE_OFFSET = 164
SUMMARY_STATE_RESUME_AFTER_SWITCH_OFFSET = 165
SUMMARY_STATE_OWNER_POKEMON_OFFSET = 168
SUMMARY_STATE_RETAIL_SIZE = 0x7D8
SUMMARY_STATE_EXTENSION_SIZE = 0xC0
SUMMARY_OWNER_DIRTY_OFFSET = 0x38
SUMMARY_OWNER_ARGS_SIZE = 0x3C
SUMMARY_BASE_MOVE_OFFSET = 0x18
SUMMARY_BASE_POS_OFFSET = 0x14
SUMMARY_BASE_LIMIT_OFFSET = 0x13
SUMMARY_BASE_DATA_TYPE_OFFSET = 0x11
SUMMARY_BASE_POINTER_OFFSET = 0x22C
SUMMARY_PAGE_MODE_OFFSET = 0x7BC
SUMMARY_TRANSITION_OFFSET = 0x7BF
SUMMARY_CACHE_MOVES_OFFSET = 0x264
SUMMARY_CACHE_CUR_PP_OFFSET = 0x26C
SUMMARY_CACHE_MAX_PP_OFFSET = 0x270
MAIN_OVERLAY_TABLE = 0x021D0DF0
OVERLAY_ENTRY_SIZE = 8
OVERLAY_SLOT_COUNT = 8
SUMMARY_RELEARN_OVERLAY_ID = 154
TASK6_DAYCARE_MAP = 38
TASK6_DAYCARE_STORY_VAR_OFFSET = 0x8E * 2
TASK6_DAYCARE_EXTERIOR = (368, 411)
TASK6_DAYCARE_PARTY_MOVES = (57, 48, 109, 0)
TASK6_DAYCARE_DEPOSITED_MOVES = (57, 48, 282, 0)
TASK6_DAYCARE_PARTY_NEW_PP = 8
TASK6_DAYCARE_DEPOSITED_NEW_PP = 8
TASK6_DAYCARE_PARTY_HISTORY = CONTROLLED_HISTORY_MOVES + (109,)
TASK6_DAYCARE_DEPOSITED_HISTORY = (57, 48, 282)
GFIELD_SYSTEM_POINTER = 0x023DFFB4
FUNC_EVENT_SET_SCRIPT = 0x0203FE74


if not all(
    name in globals()
    for name in (
        "MANIFEST",
        "HEADLESS",
        "PARTY",
        "BOOTSTRAP_AUTHENTICATION",
        "BOOTSTRAP_REAUTHENTICATE",
        "BOOTSTRAP_MANIFEST_PATH",
        "BOOTSTRAP_ROM_PATH",
        "BOOTSTRAP_LAUNCHER_PATH",
        "BOOTSTRAP_LIBDESMUME_PATH",
        "BOOTSTRAP_PYTHON_PATH",
        "BOOTSTRAP_CHILD_ENVIRONMENT",
    )
):
    raise RuntimeError(
        "run Summary relearn acceptance through "
        "launch_summary_move_relearn_runtime.py"
    )

from desmume.emulator import DeSmuME  # noqa: E402


SUBPROCESS_AUTHENTICATION_ARGS: list[str] = []


class EvidenceArtifactRegistry:
    """Freeze and content-address files referenced by runtime evidence."""

    _SINGLE_CLAIM_KEYS = {
        "capture",
        "party_exit_screenshot",
        "exported_raw_save",
    }
    _MULTI_CLAIM_KEYS = {"captures", "screenshots"}

    def __init__(self) -> None:
        self._protected: set[str] = set()
        self._entries: dict[str, dict[str, object]] = {}
        self._lexical_paths: dict[str, str] = {}
        self._file_identities: dict[tuple[int, int], str] = {}

    @staticmethod
    def _canonical(path: Path) -> tuple[str, str]:
        lexical = os.path.abspath(os.fspath(path))
        canonical = os.path.realpath(lexical)
        require(
            lexical == canonical,
            f"evidence artifact path uses an alias: {lexical}",
        )
        return lexical, canonical

    def protect(self, *paths: Path | None) -> None:
        for path in paths:
            if path is None:
                continue
            _, canonical = self._canonical(path)
            self._protected.add(canonical)

    def prepare_target(self, path: Path) -> Path:
        lexical, canonical = self._canonical(path)
        require(
            canonical not in self._protected,
            f"evidence artifact aliases a protected input/output: {canonical}",
        )
        require(
            canonical not in self._entries,
            f"frozen evidence artifact cannot be overwritten: {canonical}",
        )
        prior = self._lexical_paths.get(canonical)
        require(
            prior is None or prior == lexical,
            f"distinct evidence paths alias one file: {prior}, {lexical}",
        )
        self._lexical_paths[canonical] = lexical
        Path(canonical).parent.mkdir(parents=True, exist_ok=True)
        return Path(canonical)

    @staticmethod
    def _hash_descriptor(descriptor: int) -> dict[str, object]:
        digest = hashlib.sha256()
        size = 0
        os.lseek(descriptor, 0, os.SEEK_SET)
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
        os.lseek(descriptor, 0, os.SEEK_SET)
        return {"size": size, "sha256": digest.hexdigest()}

    @staticmethod
    def _identity(info: os.stat_result) -> tuple[int, int, int, int]:
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)

    def register(
        self,
        path: Path,
        *,
        expected: dict[str, object] | None = None,
    ) -> dict[str, object]:
        lexical, canonical = self._canonical(path)
        require(
            canonical not in self._protected,
            f"evidence artifact aliases a protected input/output: {canonical}",
        )
        existing = self._entries.get(canonical)
        if existing is not None:
            record = dict(existing["record"])
            if expected is not None:
                require(
                    record == expected,
                    f"evidence artifact record differs: {canonical}",
                )
            return record
        prior = self._lexical_paths.get(canonical)
        require(
            prior is None or prior == lexical,
            f"distinct evidence paths alias one file: {prior}, {lexical}",
        )
        info = os.lstat(canonical)
        require(
            stat.S_ISREG(info.st_mode),
            f"evidence artifact is not regular: {canonical}",
        )
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(canonical, flags)
        try:
            opened = os.fstat(descriptor)
            require(
                self._identity(opened) == self._identity(info),
                f"evidence artifact changed while opening: {canonical}",
            )
            content = self._hash_descriptor(descriptor)
            require(
                content["size"] == opened.st_size,
                f"evidence artifact size changed while hashing: {canonical}",
            )
            record = {"path": canonical, **content}
            file_identity = (opened.st_dev, opened.st_ino)
            identity_owner = self._file_identities.get(file_identity)
            require(
                identity_owner is None or identity_owner == canonical,
                "distinct evidence paths alias one inode: "
                f"{identity_owner}, {canonical}",
            )
            if expected is not None:
                require(
                    record == expected,
                    f"evidence artifact record differs: {canonical}",
                )
            self._entries[canonical] = {
                "descriptor": descriptor,
                "identity": self._identity(opened),
                "record": record,
            }
            self._lexical_paths[canonical] = lexical
            self._file_identities[file_identity] = canonical
            descriptor = -1
            return dict(record)
        finally:
            if descriptor >= 0:
                os.close(descriptor)

    def reauthenticate(self) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for canonical in sorted(self._entries):
            entry = self._entries[canonical]
            require(
                os.path.realpath(os.path.abspath(canonical)) == canonical,
                f"evidence artifact path changed identity: {canonical}",
            )
            info = os.lstat(canonical)
            require(
                stat.S_ISREG(info.st_mode),
                f"evidence artifact became non-regular: {canonical}",
            )
            descriptor = int(entry["descriptor"])
            opened = os.fstat(descriptor)
            require(
                self._identity(info) == entry["identity"]
                and self._identity(opened) == entry["identity"],
                f"evidence artifact identity changed: {canonical}",
            )
            content = self._hash_descriptor(descriptor)
            record = dict(entry["record"])
            require(
                content == {"size": record["size"], "sha256": record["sha256"]},
                f"evidence artifact content changed: {canonical}",
            )
            records.append(record)
        return records

    @staticmethod
    def _is_record(value: object) -> bool:
        return (
            isinstance(value, dict)
            and set(value) == {"path", "size", "sha256"}
            and isinstance(value.get("path"), str)
            and isinstance(value.get("size"), int)
            and isinstance(value.get("sha256"), str)
        )

    def _claim_record(self, value: object) -> dict[str, object]:
        if self._is_record(value):
            expected = dict(value)
            return self.register(Path(str(expected["path"])), expected=expected)
        require(
            isinstance(value, str),
            "evidence artifact claim is not a path or record",
        )
        return self.register(Path(value))

    def transform_claims(self, value: object, parent_key: str = "") -> object:
        if parent_key in self._SINGLE_CLAIM_KEYS:
            return self._claim_record(value)
        if parent_key in self._MULTI_CLAIM_KEYS:
            require(
                isinstance(value, list),
                f"{parent_key} artifact claims are malformed",
            )
            return [self._claim_record(item) for item in value]
        if parent_key == "records" and self._is_record(value):
            return self._claim_record(value)
        if isinstance(value, dict):
            return {
                key: self.transform_claims(item, key)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self.transform_claims(item, parent_key) for item in value]
        return value


EVIDENCE_ARTIFACTS = EvidenceArtifactRegistry()


def artifact_authentication(
    rom: Path,
    publication_manifest: Path,
) -> dict[str, object]:
    require(
        rom.resolve() == Path(BOOTSTRAP_ROM_PATH).resolve(),
        "runtime ROM path differs from authenticated bootstrap",
    )
    require(
        publication_manifest.resolve()
        == Path(BOOTSTRAP_MANIFEST_PATH).resolve(),
        "publication manifest path differs from authenticated bootstrap",
    )
    authentication = BOOTSTRAP_REAUTHENTICATE()
    require(
        authentication == BOOTSTRAP_AUTHENTICATION,
        "bootstrap authentication record changed before runtime",
    )
    return authentication


def validate_expected_authentication(
    authentication: dict[str, object],
    *,
    expected_manifest_sha256: str | None,
    expected_launcher_sha256: str | None,
    expected_verifier_sha256: str | None,
) -> None:
    manifest_record = authentication["publication_manifest"]
    launcher_record = authentication["runtime_launcher"]
    verifier_record = authentication["runtime_verifier"]
    require(
        isinstance(manifest_record, dict)
        and isinstance(launcher_record, dict)
        and isinstance(verifier_record, dict),
        "runtime artifact authentication records are malformed",
    )
    if expected_manifest_sha256 is not None:
        require(
            manifest_record.get("sha256") == expected_manifest_sha256,
            "publication manifest SHA-256 differs from the required artifact",
        )
    if expected_launcher_sha256 is not None:
        require(
            launcher_record.get("sha256") == expected_launcher_sha256,
            "runtime launcher SHA-256 differs from the required revision",
        )
    if expected_verifier_sha256 is not None:
        require(
            verifier_record.get("sha256") == expected_verifier_sha256,
            "runtime verifier SHA-256 differs from the required revision",
        )


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_artifact_path(path: Path, writer: object) -> dict[str, object]:
    final = EVIDENCE_ARTIFACTS.prepare_target(path)
    temporary_directory = Path(tempfile.mkdtemp(
        prefix=f".{final.name}.artifact.", dir=final.parent
    ))
    temporary = temporary_directory / (
        "payload" + (final.suffix or ".tmp")
    )
    try:
        require(callable(writer), "evidence artifact writer is not callable")
        require(
            writer(temporary) is not False,
            f"could not create evidence artifact: {final}",
        )
        info = os.lstat(temporary)
        require(
            stat.S_ISREG(info.st_mode),
            f"temporary evidence artifact is not regular: {temporary}",
        )
        descriptor = os.open(
            temporary, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        )
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(temporary, final)
        _fsync_directory(final.parent)
        return EVIDENCE_ARTIFACTS.register(final)
    finally:
        if temporary.exists():
            temporary.unlink()
        temporary_directory.rmdir()


def export_backup_artifact(emu: DeSmuME, path: Path) -> dict[str, object]:
    return _atomic_artifact_path(
        path,
        lambda temporary: emu.backup.export_file(str(temporary)),
    )


def artifact_path(value: object) -> Path:
    if EVIDENCE_ARTIFACTS._is_record(value):
        return Path(str(EVIDENCE_ARTIFACTS._claim_record(value)["path"]))
    require(isinstance(value, str), "artifact path claim is malformed")
    return Path(value)


def _canonical_result_payload(result: dict[str, object]) -> bytes:
    payload = dict(result)
    payload.pop("result_authentication", None)
    return (
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def authenticate_result(result: dict[str, object]) -> dict[str, object]:
    transformed = EVIDENCE_ARTIFACTS.transform_claims(result)
    require(isinstance(transformed, dict), "runtime result is not an object")
    records = EVIDENCE_ARTIFACTS.reauthenticate()
    rendered_records = (
        json.dumps(records, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    transformed["evidence_artifacts"] = {
        "schema": "summary-move-relearn-evidence-artifacts-v1",
        "records": records,
        "sha256": hashlib.sha256(rendered_records).hexdigest(),
    }
    payload = _canonical_result_payload(transformed)
    transformed["result_authentication"] = {
        "schema": "summary-move-relearn-result-v1",
        "size": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    return transformed


def verify_authenticated_result(result: dict[str, object]) -> None:
    authentication = result.get("result_authentication")
    require(
        isinstance(authentication, dict)
        and set(authentication) == {"schema", "size", "sha256"}
        and authentication.get("schema") == "summary-move-relearn-result-v1",
        "child result authentication is malformed",
    )
    payload = _canonical_result_payload(result)
    require(
        authentication.get("size") == len(payload)
        and authentication.get("sha256") == hashlib.sha256(payload).hexdigest(),
        "child result authentication differs",
    )
    artifacts = result.get("evidence_artifacts")
    require(
        isinstance(artifacts, dict)
        and set(artifacts) == {"schema", "records", "sha256"}
        and artifacts.get("schema")
        == "summary-move-relearn-evidence-artifacts-v1"
        and isinstance(artifacts.get("records"), list),
        "child evidence artifact authentication is malformed",
    )
    records = artifacts["records"]
    rendered_records = (
        json.dumps(records, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    require(
        artifacts.get("sha256") == hashlib.sha256(rendered_records).hexdigest(),
        "child evidence artifact set authentication differs",
    )
    for record in records:
        EVIDENCE_ARTIFACTS._claim_record(record)


def write_result_atomic(path: Path, rendered: str) -> None:
    EVIDENCE_ARTIFACTS.reauthenticate()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
        require(
            path.read_text(encoding="utf-8") == rendered,
            "published result bytes differ",
        )
        EVIDENCE_ARTIFACTS.reauthenticate()
        require(
            BOOTSTRAP_REAUTHENTICATE() == BOOTSTRAP_AUTHENTICATION,
            "runtime closure changed after result publication",
        )
    except Exception:
        if path.exists():
            path.unlink()
            _fsync_directory(path.parent)
        raise
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def boot_arguments() -> SimpleNamespace:
    return SimpleNamespace(
        boot_frames=420,
        ready_a_taps=10,
        tap_hold_frames=24,
        tap_gap_frames=36,
        load_frames=300,
    )


def tap(emu: DeSmuME, key: str, gap: int = 60) -> None:
    HEADLESS.tap_key(emu, key, 2, gap)


def touch(emu: DeSmuME, x: int, y: int, gap: int = 60) -> None:
    emu.input.touch_set_pos(x, y)
    HEADLESS.cycle(emu, 8)
    emu.input.touch_release()
    HEADLESS.cycle(emu, gap)


def screenshot(emu: DeSmuME, root: Path, name: str) -> str:
    path = root / name
    record = _atomic_artifact_path(
        path,
        lambda temporary: emu.screenshot().save(temporary, format="PNG"),
    )
    return str(record["path"])


def save_data_pointer(emu: DeSmuME) -> int:
    pointer = emu.memory.unsigned[
        SAVE_DATA_POINTER:SAVE_DATA_POINTER:4
    ]
    require(
        0x02000000 <= pointer < 0x02400000,
        f"invalid SaveData pointer 0x{pointer:08X}",
    )
    return pointer


def read_bytes(emu: DeSmuME, address: int, size: int) -> bytes:
    return bytes(emu.memory.unsigned[address:address + size:1])


def read_u8(emu: DeSmuME, address: int) -> int:
    return emu.memory.unsigned[address:address:1]


def read_u16(emu: DeSmuME, address: int) -> int:
    return emu.memory.unsigned[address:address:2]


def read_u32(emu: DeSmuME, address: int) -> int:
    return emu.memory.unsigned[address:address:4]


def write_bytes(emu: DeSmuME, address: int, data: bytes) -> None:
    emu.memory.unsigned[address:address + len(data):1] = data


def write_u8(emu: DeSmuME, address: int, value: int) -> None:
    write_bytes(emu, address, bytes((value & 0xFF,)))


def write_u16(emu: DeSmuME, address: int, value: int) -> None:
    write_bytes(emu, address, struct.pack("<H", value))


def write_u32(emu: DeSmuME, address: int, value: int) -> None:
    write_bytes(emu, address, struct.pack("<I", value))


def invoke_packaged_mailbox_operation(
    emu: DeSmuME,
    operation: int,
    entry: int,
    *,
    boxno: int = 0,
    slotno: int = 0,
    walker_counter_seed: int = 0,
) -> dict[str, object]:
    """Ask the game-native dispatcher to execute one fixed packaged entry.

    The host only publishes a sealed task-6 mailbox request and cycles the
    emulator normally. The already-running field-ready task consumes it from
    a canonical Thumb execution context. A read-only exec callback proves the
    requested fixed entry was actually fetched; no host register or PC writes
    participate in this evidence.
    """
    allowed = {
        TASK6_POKEWALKER_OP_STAGE: TASK6_POKEWALKER_STAGE_ENTRY,
        TASK6_POKEWALKER_OP_ACK_FIRST: TASK6_POKEWALKER_ACK_FIRST_ENTRY,
        TASK6_POKEWALKER_OP_ACK_SECOND: TASK6_POKEWALKER_ACK_SECOND_ENTRY,
        TASK6_POKEWALKER_OP_RECOVER: TASK6_POKEWALKER_RECOVERY_ENTRY,
    }
    require(
        allowed.get(operation) == entry,
        "mailbox operation does not select the required packaged entry",
    )
    completion_before = read_u32(emu, TASK6_POKEWALKER_MAILBOX + 0x0C)
    request_sequence = (completion_before + 1) & 0xFFFFFFFF
    require(request_sequence != 0, "task-6 mailbox sequence wrapped")
    state: dict[str, object] = {
        "entry_hits": 0,
        "poll_hits": 0,
    }

    def entry_hit(_address: int, _size: int) -> None:
        state["entry_hits"] = int(state["entry_hits"]) + 1

    def poll_hit(_address: int, _size: int) -> None:
        state["poll_hits"] = int(state["poll_hits"]) + 1

    emu.memory.register_exec(entry, entry_hit)
    emu.memory.register_exec(TASK6_POKEWALKER_DIAGNOSTIC_POLL, poll_hit)
    try:
        # Magic is the release word and is published only after every payload
        # field. The in-ROM consumer clears it before calling packaged code.
        write_u32(emu, TASK6_POKEWALKER_MAILBOX + 0x00, 0)
        write_u32(
            emu,
            TASK6_POKEWALKER_MAILBOX + 0x04,
            TASK6_POKEWALKER_MAILBOX_VERSION,
        )
        write_u32(emu, TASK6_POKEWALKER_MAILBOX + 0x08, request_sequence)
        write_u32(emu, TASK6_POKEWALKER_MAILBOX + 0x10, operation)
        write_u32(emu, TASK6_POKEWALKER_MAILBOX + 0x14, boxno)
        write_u32(emu, TASK6_POKEWALKER_MAILBOX + 0x18, slotno)
        write_u32(emu, TASK6_POKEWALKER_MAILBOX + 0x1C, 0)
        write_u32(emu, TASK6_POKEWALKER_MAILBOX + 0x20, 0)
        write_u32(
            emu,
            TASK6_POKEWALKER_MAILBOX + 0x24,
            walker_counter_seed,
        )
        write_u32(emu, TASK6_POKEWALKER_MAILBOX + 0x28, 0)
        write_u32(emu, TASK6_POKEWALKER_MAILBOX + 0x2C, 0)
        write_u32(
            emu,
            TASK6_POKEWALKER_MAILBOX + 0x00,
            TASK6_POKEWALKER_MAILBOX_MAGIC,
        )
        for _ in range(240):
            HEADLESS.cycle(emu, 1)
            if (
                read_u32(emu, TASK6_POKEWALKER_MAILBOX + 0x0C)
                == request_sequence
            ):
                break
        require(
            read_u32(emu, TASK6_POKEWALKER_MAILBOX + 0x0C)
            == request_sequence
            and read_u32(emu, TASK6_POKEWALKER_MAILBOX + 0x20)
            == TASK6_POKEWALKER_STATUS_COMPLETE
            and read_u32(emu, TASK6_POKEWALKER_MAILBOX + 0x00) == 0
            and state["entry_hits"] == 1
            and int(state["poll_hits"]) >= 1,
            "packaged mailbox diagnostic did not complete one exact entry: "
            f"op={operation} entry=0x{entry:08X} state={state}",
        )
    finally:
        emu.memory.register_exec(entry, None)
        emu.memory.register_exec(TASK6_POKEWALKER_DIAGNOSTIC_POLL, None)
    return {
        "operation": operation,
        "entry": f"0x{entry:08X}",
        "entry_hits": state["entry_hits"],
        "dispatcher": f"0x{TASK6_POKEWALKER_DIAGNOSTIC_POLL:08X}",
        "dispatcher_hits": state["poll_hits"],
        "request_sequence": request_sequence,
        "completion_sequence": read_u32(
            emu, TASK6_POKEWALKER_MAILBOX + 0x0C
        ),
        "result": read_u32(emu, TASK6_POKEWALKER_MAILBOX + 0x1C),
        "status": f"0x{read_u32(emu, TASK6_POKEWALKER_MAILBOX + 0x20):08X}",
        "walker_counter_seed": walker_counter_seed,
        "walker_counter_after": read_u32(
            emu, TASK6_POKEWALKER_MAILBOX + 0x28
        ),
        "host_pc_or_register_write": False,
    }



def overlay_registry(emu: DeSmuME) -> list[tuple[int, int]]:
    return [
        (
            read_u32(emu, MAIN_OVERLAY_TABLE + index * OVERLAY_ENTRY_SIZE),
            read_u32(
                emu,
                MAIN_OVERLAY_TABLE + index * OVERLAY_ENTRY_SIZE + 4,
            ),
        )
        for index in range(OVERLAY_SLOT_COUNT)
    ]


def overlay_is_active(emu: DeSmuME, overlay_id: int) -> bool:
    return any(
        current_id == overlay_id and active == 1
        for current_id, active in overlay_registry(emu)
    )


def wait_overlay_active(
    emu: DeSmuME,
    overlay_id: int,
    expected: bool,
    maximum_frames: int = 600,
) -> int:
    for frame in range(maximum_frames + 1):
        if overlay_is_active(emu, overlay_id) == expected:
            return frame
        HEADLESS.cycle(emu, 1)
    raise RuntimeError(
        f"overlay {overlay_id} active={expected} not reached; "
        f"registry={overlay_registry(emu)}"
    )


def runtime_party(emu: DeSmuME) -> bytes:
    return read_bytes(emu, save_data_pointer(emu) + PARTY_OFFSET, PARTY_SIZE)


def runtime_pc_storage_address(emu: DeSmuME) -> int:
    return (
        save_data_pointer(emu)
        + SAVE_DYNAMIC_REGION_OFFSET
        + PC_SAVE_OFFSET
    )


def runtime_box_address(
    emu: DeSmuME,
    box: int,
    slot: int,
) -> int:
    require(0 <= box < PC_BOX_COUNT, f"invalid runtime box index {box}")
    require(0 <= slot < PC_MONS_PER_BOX, f"invalid runtime box slot {slot}")
    return (
        runtime_pc_storage_address(emu)
        + box * PC_BOX_SIZE
        + slot * PC_MON_SIZE
    )


def runtime_box_record(
    emu: DeSmuME,
    box: int,
    slot: int,
) -> bytes:
    return read_bytes(emu, runtime_box_address(emu, box, slot), PC_MON_SIZE)


def runtime_pc_modified_flags(emu: DeSmuME) -> int:
    return read_u32(
        emu,
        runtime_pc_storage_address(emu) + PC_MODIFIED_FLAGS_OFFSET,
    )


def runtime_history(emu: DeSmuME) -> tuple[bytes, bytes]:
    save = save_data_pointer(emu)
    metadata = read_bytes(
        emu,
        save + SAVE_HISTORY_POINTER_OFFSET,
        SAVE_HISTORY_METADATA_SIZE,
    )
    pointer = struct.unpack_from("<I", metadata)[0]
    require(
        0x02000000 <= pointer < 0x02400000,
        f"invalid move-history pointer 0x{pointer:08X}",
    )
    return metadata, read_bytes(emu, pointer, HISTORY_IMAGE_SIZE)



def history_identity_count(
    history: bytes,
    personality: int,
    ot_id: int,
) -> int:
    return sum(
        struct.unpack_from("<II", record) == (personality, ot_id)
        for record in history_records(history)
    )


def wait_party_locked(
    emu: DeSmuME,
    maximum_frames: int = 90,
) -> bytes:
    for _ in range(maximum_frames + 1):
        party = runtime_party(emu)
        flags = [
            struct.unpack_from("<H", party, 8 + index * 0xEC + 4)[0]
            for index in range(6)
        ]
        if all((flag & 3) == 0 for flag in flags):
            return party
        emu.cycle(1)
    raise RuntimeError("party accessors did not restore encrypted record state")


def record_payload(record: bytes) -> tuple[bytes, tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    box = record[:0x88]
    pid = struct.unpack_from("<I", box)[0]
    payload = PARTY.decrypt_box_payload(box)
    permutation = (pid & 0x3E000) >> 13
    attacks = PARTY.SUBSTRUCT_OFFSETS[permutation][1]
    moves = struct.unpack_from("<4H", payload, attacks)
    pp = struct.unpack_from("<4B", payload, attacks + 8)
    pp_ups = struct.unpack_from("<4B", payload, attacks + 12)
    return payload, moves, pp, pp_ups


def party_record(party: bytes, slot: int) -> bytes:
    start = 8 + slot * 0xEC
    return party[start:start + 0xEC]


def encrypt_box_payload(payload: bytes, checksum: int) -> bytes:
    seed = checksum
    encrypted = bytearray(payload)
    for offset in range(0, len(encrypted), 2):
        seed = (seed * 1103515245 + 24691) & 0xFFFFFFFF
        word = struct.unpack_from("<H", encrypted, offset)[0]
        struct.pack_into("<H", encrypted, offset, word ^ (seed >> 16))
    return bytes(encrypted)


def controlled_party_record(record: bytes) -> bytes:
    payload, _, _, _ = record_payload(record)
    payload_data = bytearray(payload)
    pid = struct.unpack_from("<I", record)[0]
    permutation = (pid & 0x3E000) >> 13
    attacks = PARTY.SUBSTRUCT_OFFSETS[permutation][1]
    struct.pack_into("<4H", payload_data, attacks, *CONTROLLED_MOVES)
    struct.pack_into("<4B", payload_data, attacks + 8, *CONTROLLED_PP)
    struct.pack_into("<4B", payload_data, attacks + 12, *CONTROLLED_PP_UPS)
    checksum = sum(struct.unpack("<64H", payload_data)) & 0xFFFF
    controlled = bytearray(record)
    struct.pack_into("<H", controlled, 6, checksum)
    controlled[8:0x88] = encrypt_box_payload(payload_data, checksum)
    return bytes(controlled)


def box_identity(box: bytes) -> tuple[int, int, int]:
    require(len(box) == PC_MON_SIZE, "BoxPokemon record has the wrong size")
    pid = struct.unpack_from("<I", box)[0]
    payload = PARTY.decrypt_box_payload(box)
    permutation = (pid & 0x3E000) >> 13
    growth = PARTY.SUBSTRUCT_OFFSETS[permutation][0]
    species = struct.unpack_from("<H", payload, growth)[0]
    ot_id = struct.unpack_from("<I", payload, growth + 4)[0]
    return pid, ot_id, species


def box_record_payload(
    box: bytes,
) -> tuple[bytes, tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    return record_payload(box + bytes(0xEC - PC_MON_SIZE))


def controlled_box_record(
    record: bytes,
    *,
    ot_id_xor: int,
    moves: tuple[int, int, int, int] | None = None,
    pp: tuple[int, int, int, int] | None = None,
    pp_ups: tuple[int, int, int, int] | None = None,
) -> bytes:
    """Derive a distinct, authenticated BoxPokemon without changing its PID."""
    source = record[:PC_MON_SIZE]
    payload = bytearray(PARTY.decrypt_box_payload(source))
    pid = struct.unpack_from("<I", source)[0]
    permutation = (pid & 0x3E000) >> 13
    growth = PARTY.SUBSTRUCT_OFFSETS[permutation][0]
    attacks = PARTY.SUBSTRUCT_OFFSETS[permutation][1]
    original_ot_id = struct.unpack_from("<I", payload, growth + 4)[0]
    struct.pack_into("<I", payload, growth + 4, original_ot_id ^ ot_id_xor)
    if moves is not None:
        struct.pack_into("<4H", payload, attacks, *moves)
    if pp is not None:
        struct.pack_into("<4B", payload, attacks + 8, *pp)
    if pp_ups is not None:
        struct.pack_into("<4B", payload, attacks + 12, *pp_ups)
    checksum = sum(struct.unpack("<64H", payload)) & 0xFFFF
    controlled = bytearray(source)
    struct.pack_into("<H", controlled, 6, checksum)
    controlled[8:] = encrypt_box_payload(bytes(payload), checksum)
    validate_box_checksum(bytes(controlled), "controlled BoxPokemon")
    return bytes(controlled)


def authenticated_box_variant(
    box: bytes,
    *,
    species: int | None = None,
    form: int | None = None,
    is_egg: bool | None = None,
) -> bytes:
    """Patch named BoxPokemon fields and reauthenticate its encrypted payload."""
    require(len(box) == PC_MON_SIZE, "variant BoxPokemon has wrong size")
    payload = bytearray(PARTY.decrypt_box_payload(box))
    pid = struct.unpack_from("<I", box)[0]
    permutation = (pid & 0x3E000) >> 13
    growth = PARTY.SUBSTRUCT_OFFSETS[permutation][0]
    attacks = PARTY.SUBSTRUCT_OFFSETS[permutation][1]
    if species is not None:
        struct.pack_into("<H", payload, growth, species)
    if is_egg is not None:
        iv_word = struct.unpack_from("<I", payload, attacks + 0x10)[0]
        if is_egg:
            iv_word |= 1 << 30
        else:
            iv_word &= ~(1 << 30)
        struct.pack_into("<I", payload, attacks + 0x10, iv_word)
    if form is not None:
        require(0 <= form < 32, "serialized form is not five-bit")
        form_byte = payload[attacks + 0x18]
        payload[attacks + 0x18] = (form_byte & 0x07) | (form << 3)
    checksum = sum(struct.unpack("<64H", payload)) & 0xFFFF
    variant = bytearray(box)
    struct.pack_into("<H", variant, 6, checksum)
    variant[8:] = encrypt_box_payload(bytes(payload), checksum)
    validate_box_checksum(bytes(variant), "authenticated invalid fixture")
    return bytes(variant)


def checksum_failed_box_variant(box: bytes) -> bytes:
    """Set BoxPokemon.checksum_fail without invoking a data accessor."""
    require(len(box) == PC_MON_SIZE, "checksum fixture has wrong size")
    variant = bytearray(box)
    struct.pack_into("<H", variant, 4, struct.unpack_from("<H", box, 4)[0] | 4)
    return bytes(variant)


def validate_box_checksum(box: bytes, label: str) -> dict[str, int | bool]:
    require(len(box) == PC_MON_SIZE, f"{label} has the wrong serialized size")
    stored = struct.unpack_from("<H", box, 6)[0]
    payload = PARTY.decrypt_box_payload(box)
    calculated = sum(struct.unpack("<64H", payload)) & 0xFFFF
    require(
        stored == calculated,
        f"{label} checksum 0x{stored:04X} != 0x{calculated:04X}",
    )
    pid, ot_id, species = box_identity(box)
    return {
        "stored": stored,
        "calculated": calculated,
        "valid": True,
        "pid": pid,
        "ot_id": ot_id,
        "species": species,
    }


def serialized_form_and_egg(box: bytes) -> tuple[int, bool]:
    payload = PARTY.decrypt_box_payload(box)
    personality = struct.unpack_from("<I", box)[0]
    permutation = (personality & 0x3E000) >> 13
    attacks = PARTY.SUBSTRUCT_OFFSETS[permutation][1]
    iv_word = struct.unpack_from("<I", payload, attacks + 0x10)[0]
    return (payload[attacks + 0x18] >> 3, bool(iv_word & (1 << 30)))


def pc_box_record(raw: bytes, base: int, box: int, slot: int) -> bytes:
    require(0 <= box < PC_BOX_COUNT, f"invalid box index {box}")
    require(0 <= slot < PC_MONS_PER_BOX, f"invalid box slot {slot}")
    start = base + PC_SAVE_OFFSET + box * PC_BOX_SIZE + slot * PC_MON_SIZE
    return raw[start:start + PC_MON_SIZE]


def valid_pc_copies(raw: bytes) -> list[tuple[int, int]]:
    copies: list[tuple[int, int]] = []
    for base in PARTY.SAVE_COPY_BASES:
        footer = base + PC_SAVE_OFFSET + PC_SAVE_SIZE - PC_FOOTER_SIZE
        counter, size, magic, slot, crc = struct.unpack_from(
            "<IIIHH", raw, footer
        )
        if (
            size == PC_SAVE_SIZE
            and magic == PARTY.SAVE_MAGIC
            and slot == PC_SAVE_SLOT
            and crc
            == PARTY.crc16_ccitt_false(
                raw[base + PC_SAVE_OFFSET:footer]
            )
        ):
            copies.append((counter, base))
    return copies


def active_pc_copy(raw: bytes) -> tuple[int, int]:
    copies = valid_pc_copies(raw)
    require(copies, "raw save has no valid authenticated PC generation")
    selected = copies[0]
    for candidate in copies[1:]:
        if PARTY.save_counter_compare(candidate[0], selected[0]) > 0:
            selected = candidate
    return selected


def validate_all_boxed_checksums(
    raw: bytes,
    base: int,
) -> list[dict[str, int | bool]]:
    results: list[dict[str, int | bool]] = []
    for box in range(PC_BOX_COUNT):
        for slot in range(PC_MONS_PER_BOX):
            record = pc_box_record(raw, base, box, slot)
            checked = validate_box_checksum(
                record, f"serialized PC box {box} slot {slot}"
            )
            results.append({"box": box, "slot": slot, **checked})
    return results


def validate_all_party_checksums(party: bytes) -> list[dict[str, int | bool]]:
    results: list[dict[str, int | bool]] = []
    for index in range(6):
        box = party_record(party, index)[:0x88]
        stored = struct.unpack_from("<H", box, 6)[0]
        payload = PARTY.decrypt_box_payload(box)
        calculated = sum(struct.unpack("<64H", payload)) & 0xFFFF
        require(
            stored == calculated,
            f"serialized party slot {index} checksum "
            f"0x{stored:04X} != 0x{calculated:04X}",
        )
        results.append(
            {
                "slot": index,
                "stored": stored,
                "calculated": calculated,
                "valid": True,
            }
        )
    return results


def locate_summary_relearn_state(
    emu: DeSmuME,
    original_moves: tuple[int, ...] = CONTROLLED_MOVES,
    owner_pos: int = TARGET_SLOT,
    minimum_candidates: int = 1,
) -> int:
    signature = struct.pack("<4H", *original_moves)
    for chunk_address in range(0x02000000, 0x02400000, 0x10000):
        chunk = read_bytes(emu, chunk_address, 0x10000)
        offset = chunk.find(signature)
        while offset >= 0:
            original_moves = chunk_address + offset
            state = original_moves - SUMMARY_STATE_ORIGINAL_MOVES_OFFSET
            if (
                state >= 0x02000000
                and read_u16(
                    emu,
                    state + SUMMARY_STATE_CANDIDATE_COUNT_OFFSET,
                ) >= minimum_candidates
                and read_u8(
                    emu,
                    state + SUMMARY_STATE_OWNER_POS_OFFSET,
                ) == owner_pos
            ):
                owner = read_u32(emu, state)
                require(
                    0x02000000 <= owner < 0x02400000,
                    f"invalid Summary owner pointer 0x{owner:08X}",
                )
                require(
                    state - SUMMARY_STATE_RETAIL_SIZE >= 0x02000000,
                    "Summary relearn state is not appended to retail state",
                )
                return state
            offset = chunk.find(signature, offset + 1)
    raise RuntimeError("could not locate live Summary relearn state")


def locate_inactive_summary_state(
    emu: DeSmuME,
    moves: tuple[int, ...] = CONTROLLED_MOVES,
    owner_pos: int | None = TARGET_SLOT,
    data_type: int | None = 1,
    page_mode: int | None = 1,
) -> int:
    signature = struct.pack("<4H", *moves)
    for chunk_address in range(0x02000000, 0x02400000, 0x10000):
        chunk = read_bytes(emu, chunk_address, 0x10000)
        offset = chunk.find(signature)
        while offset >= 0:
            summary = (
                chunk_address + offset - SUMMARY_CACHE_MOVES_OFFSET
            )
            owner = (
                read_u32(emu, summary + SUMMARY_BASE_POINTER_OFFSET)
                if summary >= 0x02000000
                else 0
            )
            if (
                0x02000000 <= owner < 0x02400000
                and (
                    data_type is None
                    or read_u8(
                        emu, owner + SUMMARY_BASE_DATA_TYPE_OFFSET
                    )
                    == data_type
                )
                and (
                    owner_pos is None
                    or read_u8(emu, owner + SUMMARY_BASE_POS_OFFSET)
                    == owner_pos
                )
                and (
                    page_mode is None
                    or read_u8(emu, summary + SUMMARY_PAGE_MODE_OFFSET)
                    == page_mode
                )
            ):
                return summary + SUMMARY_STATE_RETAIL_SIZE
            offset = chunk.find(signature, offset + 1)
    raise RuntimeError("could not locate inactive Summary state")


def candidate_state(emu: DeSmuME, state: int) -> dict[str, object]:
    count = read_u16(emu, state + SUMMARY_STATE_CANDIDATE_COUNT_OFFSET)
    cursor = read_u16(emu, state + SUMMARY_STATE_CANDIDATE_CURSOR_OFFSET)
    top = read_u16(emu, state + SUMMARY_STATE_CANDIDATE_TOP_OFFSET)
    candidates = struct.unpack(
        f"<{count}H",
        read_bytes(emu, state + 4, count * 2),
    ) if count else ()
    summary = state - SUMMARY_STATE_RETAIL_SIZE
    cache_moves = struct.unpack(
        "<4H",
        read_bytes(emu, summary + SUMMARY_CACHE_MOVES_OFFSET, 8),
    )
    cache_cur = tuple(
        read_bytes(emu, summary + SUMMARY_CACHE_CUR_PP_OFFSET, 4)
    )
    cache_max = tuple(
        read_bytes(emu, summary + SUMMARY_CACHE_MAX_PP_OFFSET, 4)
    )
    return {
        "count": count,
        "cursor": cursor,
        "top": top,
        "candidates": candidates,
        "cache_moves": cache_moves,
        "cache_cur_pp": cache_cur,
        "cache_max_pp": cache_max,
    }


def assert_candidate_viewport(
    emu: DeSmuME,
    state: int,
    expected_cursor: int,
    expected_top: int,
    label: str,
) -> dict[str, object]:
    evidence = candidate_state(emu, state)
    require(
        evidence["cursor"] == expected_cursor
        and evidence["top"] == expected_top,
        f"{label} cursor/top differs: "
        f"{evidence['cursor']}/{evidence['top']}",
    )
    candidates = evidence["candidates"]
    visible = tuple(candidates[expected_top:expected_top + 4])
    padded = visible + (0,) * (4 - len(visible))
    require(
        evidence["cache_moves"] == padded,
        f"{label} visible candidate cache differs",
    )
    for index, move in enumerate(padded):
        current = evidence["cache_cur_pp"][index]
        maximum = evidence["cache_max_pp"][index]
        if move:
            require(
                current == maximum and maximum > 0,
                f"{label} candidate row {index} is not full PP: "
                f"{current}/{maximum}",
            )
        else:
            require(
                current == 0 and maximum == 0,
                f"{label} blank row has PP",
            )
    return evidence


def assert_prospective_slot(
    emu: DeSmuME,
    state: int,
    expected_slot: int,
    label: str,
) -> dict[str, object]:
    summary = state - SUMMARY_STATE_RETAIL_SIZE
    pending = read_u16(emu, state + SUMMARY_STATE_PENDING_MOVE_OFFSET)
    selected = read_u8(emu, state + SUMMARY_STATE_SELECTED_SLOT_OFFSET)
    moves = struct.unpack(
        "<4H",
        read_bytes(emu, summary + SUMMARY_CACHE_MOVES_OFFSET, 8),
    )
    current = tuple(
        read_bytes(emu, summary + SUMMARY_CACHE_CUR_PP_OFFSET, 4)
    )
    maximum = tuple(
        read_bytes(emu, summary + SUMMARY_CACHE_MAX_PP_OFFSET, 4)
    )
    require(selected == expected_slot, f"{label} selected slot differs")
    require(
        moves[selected] == pending and pending != 0,
        f"{label} does not show the pending move in the selected row",
    )
    require(
        current[selected] == maximum[selected] and maximum[selected] > 0,
        f"{label} prospective row is not full PP",
    )
    return {
        "label": label,
        "selected_slot": selected,
        "pending_move": pending,
        "displayed_moves": moves,
        "displayed_pp": current,
        "displayed_max_pp": maximum,
    }


def summary_state_evidence(
    emu: DeSmuME,
    state: int,
    expected_mode: int,
    expected_dirty: int,
    label: str,
) -> dict[str, int | str]:
    mode = read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET)
    owner = read_u32(emu, state)
    dirty = read_u32(emu, owner + SUMMARY_OWNER_DIRTY_OFFSET)
    require(mode == expected_mode, f"{label} mode {mode} != {expected_mode}")
    require(
        dirty == expected_dirty,
        f"{label} Summary dirty flag {dirty} != {expected_dirty}",
    )
    return {
        "label": label,
        "state": f"0x{state:08X}",
        "owner": f"0x{owner:08X}",
        "mode": mode,
        "owner_dirty": dirty,
    }


def wait_summary_identity(
    emu: DeSmuME,
    state: int,
    *,
    expected_pos: int,
    expected_mode: int,
    expected_owner_pokemon: int | None = None,
    maximum_frames: int = 360,
) -> dict[str, object]:
    summary = state - SUMMARY_STATE_RETAIL_SIZE
    for elapsed in range(maximum_frames + 1):
        owner = read_u32(emu, state)
        pos = (
            read_u8(emu, owner + SUMMARY_BASE_POS_OFFSET)
            if 0x02000000 <= owner < 0x02400000
            else 0xFF
        )
        mode = read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET)
        owner_pokemon = read_u32(
            emu, state + SUMMARY_STATE_OWNER_POKEMON_OFFSET
        )
        resume = read_u8(
            emu, state + SUMMARY_STATE_RESUME_AFTER_SWITCH_OFFSET
        )
        if (
            pos == expected_pos
            and mode == expected_mode
            and (
                expected_owner_pokemon is None
                or owner_pokemon == expected_owner_pokemon
            )
        ):
            return {
                "elapsed_frames": elapsed,
                "summary": f"0x{summary:08X}",
                "owner": f"0x{owner:08X}",
                "pos": pos,
                "mode": mode,
                "owner_pokemon": f"0x{owner_pokemon:08X}",
                "resume_after_switch": resume,
            }
        HEADLESS.cycle(emu, 1)
    raise RuntimeError(
        f"Summary identity pos={expected_pos} mode={expected_mode} "
        f"not reached; final pos={pos} mode={mode} "
        f"owner_pokemon=0x{owner_pokemon:08X} resume={resume}"
    )


def inactive_summary_evidence(
    emu: DeSmuME,
    state: int,
    label: str,
) -> dict[str, int | str]:
    summary = state - SUMMARY_STATE_RETAIL_SIZE
    owner = read_u32(emu, summary + SUMMARY_BASE_POINTER_OFFSET)
    mode = read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET)
    dirty = read_u32(emu, owner + SUMMARY_OWNER_DIRTY_OFFSET)
    require(mode == 0, f"{label} mode {mode} != 0")
    require(dirty == 0, f"{label} Summary dirty flag {dirty} != 0")
    return {
        "label": label,
        "state": f"0x{state:08X}",
        "owner": f"0x{owner:08X}",
        "mode": mode,
        "owner_dirty": dirty,
    }


def assert_fail_closed_fixture(
    emu: DeSmuME,
    state: int,
    *,
    label: str,
    expected_party: bytes,
    expected_pc: bytes,
    expected_owner_args: bytes,
    expected_metadata: bytes,
    expected_history: bytes,
) -> dict[str, object]:
    summary = state - SUMMARY_STATE_RETAIL_SIZE
    owner = read_u32(emu, summary + SUMMARY_BASE_POINTER_OFFSET)
    require(
        read_bytes(emu, state, SUMMARY_STATE_EXTENSION_SIZE)
        == bytes(SUMMARY_STATE_EXTENSION_SIZE),
        f"{label} observed candidates or entered the relearn extension",
    )
    require(
        read_bytes(emu, owner, SUMMARY_OWNER_ARGS_SIZE)
        == expected_owner_args,
        f"{label} changed Summary ownership arguments",
    )
    require(
        read_u32(emu, owner + SUMMARY_OWNER_DIRTY_OFFSET) == 0,
        f"{label} dirtied the Summary owner",
    )
    actual_party = runtime_party(emu)
    if actual_party != expected_party:
        differences = [
            index
            for index, (old, new) in enumerate(
                zip(expected_party, actual_party)
            )
            if old != new
        ]
        raise RuntimeError(
            f"{label} changed party at "
            + ",".join(f"0x{index:X}" for index in differences[:32])
        )
    actual_pc = read_bytes(
        emu, runtime_pc_storage_address(emu), PC_SAVE_SIZE
    )
    if actual_pc != expected_pc:
        differences = [
            index
            for index, (old, new) in enumerate(zip(expected_pc, actual_pc))
            if old != new
        ]
        raise RuntimeError(
            f"{label} changed PC storage at "
            + ",".join(f"0x{index:X}" for index in differences[:32])
        )
    metadata, history = runtime_history(emu)
    require(metadata == expected_metadata, f"{label} changed history metadata")
    require(history == expected_history, f"{label} changed history image")
    return {
        "label": label,
        "mode": read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET),
        "prompt_visible": read_u8(
            emu, state + SUMMARY_STATE_PROMPT_VISIBLE_OFFSET
        ),
        "candidate_count": read_u16(
            emu, state + SUMMARY_STATE_CANDIDATE_COUNT_OFFSET
        ),
        "pending_move": read_u16(
            emu, state + SUMMARY_STATE_PENDING_MOVE_OFFSET
        ),
        "owner_pokemon": read_u32(
            emu, state + SUMMARY_STATE_OWNER_POKEMON_OFFSET
        ),
        "owner_dirty": read_u32(emu, owner + SUMMARY_OWNER_DIRTY_OFFSET),
        "pc_dirty": runtime_pc_modified_flags(emu),
        "party_sha256": hashlib.sha256(expected_party).hexdigest(),
        "pc_sha256": hashlib.sha256(expected_pc).hexdigest(),
        "history_sha256": hashlib.sha256(expected_history).hexdigest(),
        "extension_zero": True,
        "no_builder_history_or_setter_observation": True,
    }


def history_records(image: bytes) -> list[bytes]:
    return [
        image[
            HISTORY_HEADER_SIZE + index * HISTORY_RECORD_SIZE:
            HISTORY_HEADER_SIZE + (index + 1) * HISTORY_RECORD_SIZE
        ]
        for index in range(HISTORY_RECORD_COUNT)
    ]


def find_history_record(
    image: bytes,
    personality: int,
    ot_id: int,
) -> tuple[int, bytes, tuple[int, ...]]:
    for index, record in enumerate(history_records(image)):
        pid, owner = struct.unpack_from("<II", record)
        move_count = record[14]
        flags = record[15]
        if flags & 1 and pid == personality and owner == ot_id:
            moves = struct.unpack_from("<24H", record, 16)[:move_count]
            return index, record, moves
    raise RuntimeError("target move-history record is missing")


def valid_history_image(image: bytes, mirror: int) -> bool:
    if len(image) != HISTORY_IMAGE_SIZE:
        return False
    try:
        (
            magic,
            version,
            header_size,
            image_size,
            capacity,
            record_count,
            moves_per_record,
            record_size,
        ) = struct.unpack_from("<IHHIHHHH", image)
        (
            footer_magic,
            _,
            payload_size,
            payload_crc,
            _,
            footer_version,
            footer_size,
            footer_mirror,
            _,
            footer_crc,
        ) = struct.unpack_from("<IIIIIHHHHI", image, HISTORY_FOOTER_OFFSET)
    except struct.error:
        return False
    occupied = sum(record[15] == 1 for record in history_records(image))
    footer = image[HISTORY_FOOTER_OFFSET:]
    return (
        magic == 0x4D484953
        and version == 1
        and header_size == HISTORY_HEADER_SIZE
        and image_size == HISTORY_IMAGE_SIZE
        and capacity == HISTORY_RECORD_COUNT
        and record_count == occupied
        and moves_per_record == 24
        and record_size == HISTORY_RECORD_SIZE
        and footer_magic == HISTORY_FOOTER_MAGIC
        and footer_version == 1
        and footer_size == 0x20
        and footer_mirror == mirror
        and payload_size == HISTORY_FOOTER_OFFSET
        and payload_crc
        == (zlib.crc32(image[:HISTORY_FOOTER_OFFSET]) & 0xFFFFFFFF)
        and footer_crc
        == (zlib.crc32(footer[:0x1C]) & 0xFFFFFFFF)
    )


def history_image_for_mirror(
    payload: bytes,
    mirror: int,
    counter: int,
) -> bytes:
    require(
        len(payload) == HISTORY_FOOTER_OFFSET,
        "history payload has the wrong size",
    )
    image = bytearray(HISTORY_IMAGE_SIZE)
    image[:HISTORY_FOOTER_OFFSET] = payload
    struct.pack_into(
        "<IIIIIHHHHI",
        image,
        HISTORY_FOOTER_OFFSET,
        HISTORY_FOOTER_MAGIC,
        counter,
        HISTORY_FOOTER_OFFSET,
        zlib.crc32(payload) & 0xFFFFFFFF,
        0,
        1,
        0x20,
        mirror,
        0,
        0,
    )
    footer_crc = zlib.crc32(
        image[HISTORY_FOOTER_OFFSET:HISTORY_FOOTER_OFFSET + 0x1C]
    ) & 0xFFFFFFFF
    struct.pack_into("<I", image, HISTORY_FOOTER_OFFSET + 0x1C, footer_crc)
    require(valid_history_image(bytes(image), mirror), "constructed history invalid")
    return bytes(image)


def seed_history_record(
    payload: bytearray,
    box: bytes,
    moves: tuple[int, ...],
) -> int:
    pid, ot_id, species = box_identity(box)
    try:
        index, _, _ = find_history_record(
            bytes(payload) + bytes(HISTORY_IMAGE_SIZE - len(payload)),
            pid,
            ot_id,
        )
    except RuntimeError:
        index = next(
            (
                candidate
                for candidate, record in enumerate(
                    history_records(
                        bytes(payload)
                        + bytes(HISTORY_IMAGE_SIZE - len(payload))
                    )
                )
                if record[15] == 0
            ),
            -1,
        )
        require(index >= 0, "controlled history has no free record")
        record_count = struct.unpack_from("<H", payload, 14)[0]
        next_access = struct.unpack_from("<I", payload, 20)[0] + 1
        struct.pack_into("<H", payload, 14, record_count + 1)
        struct.pack_into("<I", payload, 20, next_access)
        record_offset = HISTORY_HEADER_SIZE + index * HISTORY_RECORD_SIZE
        payload[record_offset:record_offset + HISTORY_RECORD_SIZE] = bytes(
            HISTORY_RECORD_SIZE
        )
        struct.pack_into(
            "<IIIHBB",
            payload,
            record_offset,
            pid,
            ot_id,
            next_access,
            species,
            0,
            1,
        )
    record_offset = HISTORY_HEADER_SIZE + index * HISTORY_RECORD_SIZE
    require(
        len(moves) <= 24 and all(move != 0 for move in moves),
        "controlled history moves are invalid",
    )
    payload[record_offset + 14] = len(moves)
    payload[record_offset + 15] = 1
    payload[record_offset + 16:record_offset + 64] = bytes(48)
    struct.pack_into(
        f"<{len(moves)}H",
        payload,
        record_offset + 16,
        *moves,
    )
    return index


def make_controlled_raw(
    baseline_raw: bytes,
) -> tuple[bytes, bytes, int, int, bytes, dict[str, object]]:
    raw = bytearray(baseline_raw)
    copies = PARTY.valid_normal_copies(baseline_raw)
    require(copies, "immutable fixture has no valid normal save copy")
    active_counter, active_base = PARTY.active_copy(baseline_raw)

    for _, base in copies:
        start = base + PARTY.PARTY_OFFSET + 8 + TARGET_SLOT * 0xEC
        record = bytes(raw[start:start + 0xEC])
        raw[start:start + 0xEC] = controlled_party_record(record)
        footer = base + PARTY.NORMAL_SAVE_SIZE - 0x10
        crc = PARTY.crc16_ccitt_false(bytes(raw[base:footer]))
        struct.pack_into("<H", raw, footer + 0x0E, crc)

    controlled_party = bytes(
        raw[
            active_base + PARTY.PARTY_OFFSET:
            active_base + PARTY.PARTY_OFFSET + PARTY.PARTY_SIZE
        ]
    )
    validate_all_party_checksums(controlled_party)
    target = party_record(controlled_party, TARGET_SLOT)
    target_payload, moves, pp, pp_ups = record_payload(target)
    require(moves == CONTROLLED_MOVES, "controlled moves were not encoded")
    require(
        pp[TARGET_REPLACEMENT_SLOT] == 1
        and pp_ups[TARGET_REPLACEMENT_SLOT] == 2,
        "controlled depleted-PP/PP-Up precondition was not encoded",
    )
    pid = struct.unpack_from("<I", target)[0]
    growth = PARTY.SUBSTRUCT_OFFSETS[(pid & 0x3E000) >> 13][0]
    ot_id = struct.unpack_from("<I", target_payload, growth + 4)[0]

    target_box = controlled_box_record(
        target,
        ot_id_xor=BOX_TARGET_OT_ID_XOR,
        moves=CONTROLLED_MOVES,
        pp=CONTROLLED_PP,
        pp_ups=CONTROLLED_PP_UPS,
    )
    switch_source = party_record(controlled_party, 3)
    _, switch_moves, switch_pp, switch_pp_ups = record_payload(switch_source)
    switch_box = controlled_box_record(
        switch_source,
        ot_id_xor=BOX_SWITCH_OT_ID_XOR,
        moves=switch_moves,
        pp=switch_pp,
        pp_ups=switch_pp_ups,
    )
    target_box_identity = box_identity(target_box)
    switch_box_identity = box_identity(switch_box)
    require(
        target_box_identity[:2] != (pid, ot_id)
        and switch_box_identity[:2] != (pid, ot_id)
        and target_box_identity[:2] != switch_box_identity[:2],
        "controlled boxed identities are not distinct",
    )
    pc_copies = valid_pc_copies(baseline_raw)
    require(
        len(pc_copies) == len(PARTY.SAVE_COPY_BASES),
        "immutable fixture does not have both valid PC generations",
    )
    for _, base in pc_copies:
        box_start = base + PC_SAVE_OFFSET
        raw[
            box_start + BOX_TARGET_SLOT * PC_MON_SIZE:
            box_start + (BOX_TARGET_SLOT + 1) * PC_MON_SIZE
        ] = target_box
        raw[
            box_start + BOX_SWITCH_SLOT * PC_MON_SIZE:
            box_start + (BOX_SWITCH_SLOT + 1) * PC_MON_SIZE
        ] = switch_box
        struct.pack_into("<I", raw, box_start + PC_ACTIVE_BOX_OFFSET, 0)
        struct.pack_into("<I", raw, box_start + PC_MODIFIED_FLAGS_OFFSET, 0)
        footer = base + PC_SAVE_OFFSET + PC_SAVE_SIZE - PC_FOOTER_SIZE
        crc = PARTY.crc16_ccitt_false(
            bytes(raw[base + PC_SAVE_OFFSET:footer])
        )
        struct.pack_into("<H", raw, footer + 0x0E, crc)
    require(
        len(valid_pc_copies(bytes(raw))) == len(PARTY.SAVE_COPY_BASES),
        "controlled PC generations are not authenticated",
    )

    valid_images = []
    for mirror, offset in enumerate(HISTORY_MIRROR_OFFSETS):
        image = baseline_raw[offset:offset + HISTORY_IMAGE_SIZE]
        if valid_history_image(image, mirror):
            valid_images.append(image)
    require(valid_images, "immutable fixture has no valid history mirror")
    payload = bytearray(valid_images[0][:HISTORY_FOOTER_OFFSET])
    seed_history_record(
        payload,
        target[:PC_MON_SIZE],
        CONTROLLED_HISTORY_MOVES,
    )
    target_box_history_index = seed_history_record(
        payload,
        target_box,
        CONTROLLED_HISTORY_MOVES,
    )
    switch_box_history_index = seed_history_record(
        payload,
        switch_box,
        tuple(move for move in switch_moves if move != 0),
    )
    for mirror, offset in enumerate(HISTORY_MIRROR_OFFSETS):
        counter = (
            active_counter
            if mirror == 0
            else (active_counter - 1) & 0xFFFFFFFF
        )
        image = history_image_for_mirror(bytes(payload), mirror, counter)
        raw[offset:offset + HISTORY_IMAGE_SIZE] = image
    controlled_raw = bytes(raw)
    _, active_pc_base = active_pc_copy(controlled_raw)
    active_target = pc_box_record(
        controlled_raw, active_pc_base, 0, BOX_TARGET_SLOT
    )
    active_switch = pc_box_record(
        controlled_raw, active_pc_base, 0, BOX_SWITCH_SLOT
    )
    require(
        active_target == target_box and active_switch == switch_box,
        "controlled active PC generation differs",
    )
    return (
        controlled_raw,
        controlled_party,
        pid,
        ot_id,
        bytes(payload),
        {
            "active_base": active_pc_base,
            "target": target_box,
            "switch": switch_box,
            "target_identity": target_box_identity,
            "switch_identity": switch_box_identity,
            "target_history_index": target_box_history_index,
            "switch_history_index": switch_box_history_index,
        },
    )


def make_task6_daycare_raw(
    controlled_raw: bytes,
) -> tuple[bytes, dict[str, object]]:
    """Build an authenticated fixture immediately outside the retail daycare."""
    raw = bytearray(controlled_raw)
    active_counter, active_base = PARTY.active_copy(controlled_raw)
    active_party = controlled_raw[
        active_base + PARTY.PARTY_OFFSET:
        active_base + PARTY.PARTY_OFFSET + PARTY.PARTY_SIZE
    ]
    party_source = party_record(active_party, TARGET_SLOT)
    party_box = controlled_box_record(
        party_source,
        ot_id_xor=0,
        moves=TASK6_DAYCARE_PARTY_MOVES,
        pp=(8, 8, 8, 0),
        pp_ups=(0, 0, 0, 0),
    )
    deposited_box = controlled_box_record(
        party_source,
        ot_id_xor=0x0BADF00D,
        moves=TASK6_DAYCARE_DEPOSITED_MOVES,
        pp=(8, 8, 8, 0),
        pp_ups=(0, 0, 0, 0),
    )
    party_identity = box_identity(party_box)
    deposited_identity = box_identity(deposited_box)
    require(
        party_identity[:2] != deposited_identity[:2]
        and party_identity[2] == TARGET_SPECIES
        and deposited_identity[2] == TARGET_SPECIES,
        "daycare fixture identities are not distinct same-species owners",
    )

    for _, base in PARTY.valid_normal_copies(controlled_raw):
        party_start = (
            base + PARTY.PARTY_OFFSET + 8 + TARGET_SLOT * 0xEC
        )
        existing_party = bytearray(raw[party_start:party_start + 0xEC])
        existing_party[:PC_MON_SIZE] = party_box
        raw[party_start:party_start + 0xEC] = existing_party
        raw[
            base + DAYCARE_SAVE_OFFSET:
            base + DAYCARE_SAVE_OFFSET + PC_MON_SIZE
        ] = deposited_box
        second_daycare_box = bytes(
            raw[
                base + DAYCARE_SAVE_OFFSET + DAYCARE_MON_SIZE:
                base
                + DAYCARE_SAVE_OFFSET
                + DAYCARE_MON_SIZE
                + PC_MON_SIZE
            ]
        )
        validate_box_checksum(
            second_daycare_box,
            "serialized empty second daycare owner",
        )
        require(
            box_identity(second_daycare_box)[2] == 0,
            "daycare fixture second owner is not empty",
        )

        struct.pack_into(
            "<5i",
            raw,
            base + LOCAL_FIELD_DATA_OFFSET,
            TASK6_DAYCARE_MAP,
            -1,
            TASK6_DAYCARE_EXTERIOR[0],
            TASK6_DAYCARE_EXTERIOR[1],
            0,
        )
        struct.pack_into(
            "<H",
            raw,
            base
            + VARS_FLAGS_SAVE_OFFSET
            + TASK6_DAYCARE_STORY_VAR_OFFSET,
            3,
        )
        # Continue restores serialized map objects. Retain only the canonical
        # player/follower, move them with the saved Location, and use the real
        # Route 34 door warp to load the daycare's event/NPC data.
        for index in range(2, 64):
            struct.pack_into(
                "<I",
                raw,
                base
                + SAVED_MAP_OBJECTS_OFFSET
                + index * SAVED_MAP_OBJECT_SIZE,
                0,
            )
        for index, x in ((0, 368), (1, 367)):
            object_offset = (
                base
                + SAVED_MAP_OBJECTS_OFFSET
                + index * SAVED_MAP_OBJECT_SIZE
            )
            raw[object_offset + 0x0C:object_offset + 0x0F] = bytes(3)
            struct.pack_into(
                "<hhh",
                raw,
                object_offset + 0x20,
                x,
                0,
                TASK6_DAYCARE_EXTERIOR[1],
            )
            struct.pack_into(
                "<hhh",
                raw,
                object_offset + 0x26,
                x,
                0,
                TASK6_DAYCARE_EXTERIOR[1],
            )
            struct.pack_into("<i", raw, object_offset + 0x2C, 0)

        footer = base + PARTY.NORMAL_SAVE_SIZE - 0x10
        crc = PARTY.crc16_ccitt_false(bytes(raw[base:footer]))
        struct.pack_into("<H", raw, footer + 0x0E, crc)

    _, _, selected_image = selected_persisted_history(controlled_raw)
    payload = bytearray(selected_image[:HISTORY_FOOTER_OFFSET])
    party_history_index = seed_history_record(
        payload,
        party_box,
        TASK6_DAYCARE_PARTY_HISTORY,
    )
    deposited_history_index = seed_history_record(
        payload,
        deposited_box,
        TASK6_DAYCARE_DEPOSITED_HISTORY,
    )
    for mirror, offset in enumerate(HISTORY_MIRROR_OFFSETS):
        old_image = controlled_raw[offset:offset + HISTORY_IMAGE_SIZE]
        require(
            valid_history_image(old_image, mirror),
            f"daycare fixture history mirror {mirror} is invalid",
        )
        counter = struct.unpack_from(
            "<I", old_image, HISTORY_FOOTER_OFFSET + 4
        )[0]
        raw[offset:offset + HISTORY_IMAGE_SIZE] = history_image_for_mirror(
            bytes(payload),
            mirror,
            counter,
        )

    fixture = bytes(raw)
    require(
        len(PARTY.valid_normal_copies(fixture))
        == len(PARTY.SAVE_COPY_BASES),
        "daycare fixture normal generations are not authenticated",
    )
    _, active_fixture_base = PARTY.active_copy(fixture)
    fixture_party = fixture[
        active_fixture_base + PARTY.PARTY_OFFSET:
        active_fixture_base + PARTY.PARTY_OFFSET + PARTY.PARTY_SIZE
    ]
    validate_all_party_checksums(fixture_party)
    validate_box_checksum(
        fixture[
            active_fixture_base + DAYCARE_SAVE_OFFSET:
            active_fixture_base + DAYCARE_SAVE_OFFSET + PC_MON_SIZE
        ],
        "serialized daycare owner",
    )
    return fixture, {
        "normal_save_counter": active_counter,
        "party_box": party_box,
        "party_identity": party_identity,
        "party_history_index": party_history_index,
        "deposited_box": deposited_box,
        "deposited_identity": deposited_identity,
        "deposited_history_index": deposited_history_index,
        "history_payload": bytes(payload),
    }


def assert_cancel_exact(
    emu: DeSmuME,
    expected_party: bytes,
    expected_metadata: bytes,
    expected_history: bytes,
    label: str,
) -> None:
    actual_party, _ = PARTY.wait_for_runtime_party(
        emu,
        expected_party,
        maximum_frames=90,
    )
    metadata, history = runtime_history(emu)
    if actual_party != expected_party:
        differences = [
            index
            for index, (old, new) in enumerate(
                zip(expected_party, actual_party)
            )
            if old != new
        ]
        raise RuntimeError(
            f"{label} changed party bytes at "
            + ",".join(f"0x{index:X}" for index in differences[:32])
        )
    require(metadata == expected_metadata, f"{label} changed history metadata")
    require(history == expected_history, f"{label} changed history records")


def assert_box_cancel_exact(
    emu: DeSmuME,
    expected_target: bytes,
    expected_switch: bytes,
    expected_metadata: bytes,
    expected_history: bytes,
    label: str,
) -> None:
    actual_target = runtime_box_record(emu, 0, BOX_TARGET_SLOT)
    actual_switch = runtime_box_record(emu, 0, BOX_SWITCH_SLOT)
    require(actual_target == expected_target, f"{label} changed boxed target")
    require(actual_switch == expected_switch, f"{label} changed boxed switch peer")
    require(
        runtime_pc_modified_flags(emu) == 0,
        f"{label} dirtied PC storage before a committed replacement",
    )
    metadata, history = runtime_history(emu)
    require(metadata == expected_metadata, f"{label} changed history metadata")
    require(history == expected_history, f"{label} changed history records")


def normal_save(emu: DeSmuME, baseline_counter: int) -> None:
    # Summary B -> party, party B -> active start menu, then retail SAVE.
    tap(emu, "B", 150)
    tap(emu, "B", 120)
    tap(emu, "RIGHT", 36)
    tap(emu, "A", 90)
    tap(emu, "A", 60)
    tap(emu, "A", 90)
    for _ in range(8):
        HEADLESS.tap_key(emu, "A", 24, 120)
        if PARTY.save_counter_compare(
            PARTY.read_runtime_save_counter(emu),
            baseline_counter,
        ) > 0:
            break
    require(
        PARTY.save_counter_compare(
            PARTY.read_runtime_save_counter(emu),
            baseline_counter,
        ) > 0,
        "key-only retail save did not advance the normal save counter",
    )
    HEADLESS.cycle(emu, 600)


def open_summary_info(emu: DeSmuME, party_slot: int) -> None:
    tap(emu, "X", 20)
    tap(emu, "A", 100)
    # The fixture party menu uses a two-column grid (0/1, 2/3, 4/5).
    for _ in range(party_slot // 2):
        tap(emu, "DOWN", 20)
    if party_slot % 2:
        tap(emu, "RIGHT", 20)
    tap(emu, "A", 30)
    tap(emu, "A", 100)


def open_summary_moves(emu: DeSmuME, party_slot: int) -> None:
    open_summary_info(emu, party_slot)
    tap(emu, "RIGHT", 80)


def navigate_to_moves_with_injection(
    emu: DeSmuME,
    summary: int,
    inject,
    capture,
    label: str,
) -> object:
    """Inject at the retail Info->Moves boundary before custom eligibility."""
    require(
        read_u8(emu, summary + SUMMARY_PAGE_MODE_OFFSET) != 1,
        f"{label} did not begin on Info",
    )
    key_mask = HEADLESS.keymask(HEADLESS.key_constant("RIGHT"))
    injected = False
    captured = None
    for _ in range(2):
        HEADLESS.set_key_mask(emu, key_mask)
        emu.cycle(False)
        if read_u8(emu, summary + SUMMARY_PAGE_MODE_OFFSET) == 1:
            inject()
            captured = capture()
            injected = True
            break
    HEADLESS.set_key_mask(emu, 0)
    if not injected:
        for _ in range(180):
            emu.cycle(False)
            if read_u8(emu, summary + SUMMARY_PAGE_MODE_OFFSET) == 1:
                inject()
                captured = capture()
                injected = True
                break
    require(injected, f"{label} did not reach the real Moves boundary")
    HEADLESS.cycle(emu, 80)
    return captured


def assert_malformed_navigation_consumed(
    emu: DeSmuME,
    summary: int,
    *,
    expected_page: int,
    expected_transition: int,
    label: str,
) -> None:
    require(
        read_u8(emu, summary + SUMMARY_PAGE_MODE_OFFSET)
        == expected_page
        and read_u8(emu, summary + SUMMARY_TRANSITION_OFFSET)
        == expected_transition,
        f"{label} delegated malformed navigation",
    )


def hold(emu: DeSmuME, key: str, frames: int, gap: int = 20) -> None:
    HEADLESS.hold_key(emu, key, frames, gap)


def open_retail_pc_storage_menu(
    emu: DeSmuME,
    *,
    terminal_boot: bool = False,
) -> None:
    if not terminal_boot:
        # Key-only route from the immutable fixture through the actual Center
        # warp, followed by the east aisle that avoids the moving NPC at
        # T21PC0101 (11,16).
        for key, frames in (
            ("LEFT", 90),
            ("DOWN", 150),
            ("RIGHT", 60),
            ("DOWN", 100),
            ("LEFT", 140),
            ("UP", 60),
            ("LEFT", 90),
            ("UP", 140),
        ):
            hold(emu, key, frames, 12)
        HEADLESS.cycle(emu, 300)
        for key, frames in (
            ("UP", 30),
            ("RIGHT", 60),
            ("UP", 60),
            ("LEFT", 15),
        ):
            hold(emu, key, frames)
    else:
        # The boxed post-save reload was retail-saved at the same interaction
        # tile, so only restore the facing direction.
        HEADLESS.cycle(emu, 120)
    tap(emu, "UP", 20)
    tap(emu, "A", 80)

    # Boot text -> owner selection -> Someone's PC introduction.
    for _ in range(4):
        tap(emu, "A", 60)
    tap(emu, "A", 80)
    for _ in range(3):
        tap(emu, "A", 80)


def open_retail_pc_move_ui(
    emu: DeSmuME,
    *,
    terminal_boot: bool = False,
) -> None:
    open_retail_pc_storage_menu(emu, terminal_boot=terminal_boot)
    # The storage menu starts on Deposit. Down selects Move Pokémon.
    tap(emu, "DOWN", 30)
    tap(emu, "A", 180)


def open_retail_box_summary_moves(
    emu: DeSmuME,
    screenshot_root: Path,
    prefix: str,
    *,
    terminal_boot: bool = False,
) -> tuple[int, list[str]]:
    captures: list[str] = []
    open_retail_pc_move_ui(emu, terminal_boot=terminal_boot)
    captures.append(
        screenshot(emu, screenshot_root, f"{prefix}_pc_move_ui.png")
    )

    # Touch the actual first boxed record, then its retail Summary command.
    touch(emu, 16, 56, 60)
    touch(emu, 210, 76, 180)
    captures.append(
        screenshot(emu, screenshot_root, f"{prefix}_pc_summary_info.png")
    )
    hold(emu, "RIGHT", 5, 100)
    captures.append(
        screenshot(emu, screenshot_root, f"{prefix}_pc_summary_moves.png")
    )
    state = locate_inactive_summary_state(
        emu,
        moves=box_record_payload(
            runtime_box_record(emu, 0, BOX_TARGET_SLOT)
        )[1],
        owner_pos=BOX_TARGET_SLOT,
        data_type=2,
    )
    return state, captures


def exit_pc_and_retail_save(
    emu: DeSmuME,
    baseline_counter: int,
) -> None:
    # Context menu -> box UI -> "Continue Box operations?" -> No.
    tap(emu, "B", 60)
    tap(emu, "B", 60)
    tap(emu, "DOWN", 20)
    tap(emu, "A", 180)
    # Storage operation menu -> See Ya; PC owner menu -> Switch Off.
    touch(emu, 190, 145, 180)
    touch(emu, 100, 146, 180)
    retail_save_from_field(emu, baseline_counter)


def retail_save_from_field(
    emu: DeSmuME,
    baseline_counter: int,
) -> None:
    # Retail field Save touch, text advance, explicit Yes, and completion.
    touch(emu, 125, 80, 120)
    tap(emu, "A", 90)
    tap(emu, "A", 60)
    tap(emu, "A", 90)
    for _ in range(8):
        tap(emu, "A", 120)
        if (
            PARTY.save_counter_compare(
                PARTY.read_runtime_save_counter(emu),
                baseline_counter,
            )
            > 0
        ):
            break
    require(
        PARTY.save_counter_compare(
            PARTY.read_runtime_save_counter(emu),
            baseline_counter,
        )
        > 0,
        "retail save did not advance the normal save counter",
    )
    # The counter becomes visible before all backup pages finish writing.
    HEADLESS.cycle(emu, 2000)
    # Retail returns to the still-open field menu after saving. Close it so a
    # derived bootstrap always resumes in the overworld, never by navigating
    # a persisted menu with what are intended to be movement keys.
    tap(emu, "B", 120)


def new_emulator(
    rom: Path,
    raw: bytes,
) -> tuple[DeSmuME, tempfile.NamedTemporaryFile]:
    emu = DeSmuME(BOOTSTRAP_LIBDESMUME_PATH)
    emu.volume_set(0)
    emu.open(str(rom))
    imported = tempfile.NamedTemporaryFile(suffix=".sav")
    PARTY.import_raw(emu, raw, imported)
    HEADLESS.boot_to_ready(boot_arguments(), emu)
    return emu, imported


def close_emulator(
    emu: DeSmuME,
    imported: tempfile.NamedTemporaryFile,
) -> None:
    emu.destroy()
    imported.close()


def selected_persisted_history(
    raw: bytes,
) -> tuple[int, int, bytes]:
    main_counter, _ = PARTY.active_copy(raw)
    valid: list[tuple[int, int, bytes]] = []
    for mirror, offset in enumerate(HISTORY_MIRROR_OFFSETS):
        image = raw[offset:offset + HISTORY_IMAGE_SIZE]
        if not valid_history_image(image, mirror):
            continue
        counter = struct.unpack_from("<I", image, HISTORY_FOOTER_OFFSET + 4)[0]
        if PARTY.save_counter_compare(counter, main_counter) <= 0:
            valid.append((counter, mirror, image))
    require(valid, "saved raw has no eligible authenticated history mirror")
    selected = valid[0]
    for candidate in valid[1:]:
        if PARTY.save_counter_compare(candidate[0], selected[0]) > 0:
            selected = candidate
    return selected


def assert_pp_pixels(path: Path) -> dict[str, object]:
    from PIL import Image

    image = Image.open(path).convert("RGB")
    # Candidate row 0's current/max PP glyphs on the combined 256x384 frame.
    crop = image.crop((84, 217, 112, 234))
    colors = crop.getcolors(maxcolors=2048) or []
    require(
        len(colors) >= 3,
        "candidate PP pixel crop lacks rendered text variation",
    )
    dark = sum(
        count
        for count, color in colors
        if max(color) - min(color) < 40 and sum(color) < 360
    )
    require(dark >= 4, "candidate PP crop lacks visible dark glyph pixels")
    return {
        "crop": [84, 217, 112, 234],
        "distinct_colors": len(colors),
        "dark_pixels": dark,
        "sha256": hashlib.sha256(crop.tobytes()).hexdigest(),
    }


def assert_control_pixels(
    path: Path,
    *,
    label: str,
    a_span: tuple[int, int],
    gap_span: tuple[int, int],
    b_span: tuple[int, int],
) -> dict[str, object]:
    from PIL import Image

    image = Image.open(path).convert("RGB")

    def dark_pixels(left: int, right: int) -> int:
        crop = image.crop((left, 192 + 139, right, 192 + 151))
        return sum(
            1
            for red, green, blue in crop.getdata()
            if max(red, green, blue) - min(red, green, blue) < 55
            and red + green + blue < 450
        )

    a_dark = dark_pixels(*a_span)
    gap_dark = dark_pixels(*gap_span)
    b_dark = dark_pixels(*b_span)
    require(a_dark > 0, f"{label} A/OK pixels are absent")
    require(gap_dark == 0, f"{label} dead gap contains glyph pixels")
    require(b_dark > 0, f"{label} Back-edge pixels are absent")
    return {
        "label": label,
        "y": [139, 151],
        "a_span": list(a_span),
        "gap_span": list(gap_span),
        "b_span": list(b_span),
        "a_dark_pixels": a_dark,
        "gap_dark_pixels": gap_dark,
        "b_dark_pixels": b_dark,
        "capture_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def run_reload_probe(
    rom: Path,
    raw_path: Path,
    screenshot_path: Path,
) -> dict[str, object]:
    raw = raw_path.read_bytes()
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    with HEADLESS.silence_native_output(True):
        emu, imported = new_emulator(rom, raw)
        try:
            _, _, expected_party = PARTY.party_image(raw)
            party, _ = PARTY.wait_for_runtime_party(
                emu, expected_party, maximum_frames=90
            )
            require(
                party == expected_party,
                "reload probe runtime party differs from persisted bytes",
            )
            metadata, history = runtime_history(emu)
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            screenshot(emu, screenshot_path.parent, screenshot_path.name)
        finally:
            close_emulator(emu, imported)
    return {
        "party": party.hex(),
        "metadata": metadata.hex(),
        "history": history.hex(),
    }


def fresh_reload_evidence(
    rom: Path,
    raw_path: Path,
    screenshot_path: Path,
) -> tuple[bytes, bytes, bytes]:
    completed = subprocess.run(
        [
            BOOTSTRAP_PYTHON_PATH,
            "-I",
            "-S",
            "-B",
            "-X",
            "pycache_prefix=/dev/null",
            str(Path(BOOTSTRAP_LAUNCHER_PATH).resolve()),
            "--rom",
            str(rom),
            "--probe-raw",
            str(raw_path),
            "--probe-screenshot",
            str(screenshot_path),
            *SUBPROCESS_AUTHENTICATION_ARGS,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=240,
        env=dict(BOOTSTRAP_CHILD_ENVIRONMENT),
    )
    require(
        completed.returncode == 0,
        "fresh reload probe failed: " + completed.stderr[-1000:],
    )
    probe = json.loads(completed.stdout)
    require(
        completed.stdout
        == json.dumps(probe, indent=2, sort_keys=True) + "\n",
        "fresh reload probe output is not canonical",
    )
    verify_authenticated_result(probe)
    require(
        probe.get("artifact_authentication")
        == BOOTSTRAP_AUTHENTICATION,
        "fresh reload probe artifact authentication differs",
    )
    return (
        bytes.fromhex(probe["party"]),
        bytes.fromhex(probe["metadata"]),
        bytes.fromhex(probe["history"]),
    )


def runtime_field_location(emu: DeSmuME) -> tuple[int, int, int, int, int]:
    field_system = read_u32(emu, GFIELD_SYSTEM_POINTER)
    require(
        0x02000000 <= field_system < 0x02400000,
        "runtime field-system pointer is invalid",
    )
    location = read_u32(emu, field_system + 0x20)
    require(
        0x02000000 <= location < 0x02400000,
        "runtime field location pointer is invalid",
    )
    return struct.unpack("<5i", read_bytes(emu, location, 20))


def runtime_daycare_box(emu: DeSmuME, slot: int) -> bytes:
    require(slot in (0, 1), "invalid runtime daycare slot")
    address = (
        save_data_pointer(emu)
        + SAVE_DYNAMIC_REGION_OFFSET
        + DAYCARE_SAVE_OFFSET
        + slot * DAYCARE_MON_SIZE
    )
    return read_bytes(emu, address, PC_MON_SIZE)


def runtime_daycare_image(emu: DeSmuME) -> bytes:
    return read_bytes(
        emu,
        save_data_pointer(emu)
        + SAVE_DYNAMIC_REGION_OFFSET
        + DAYCARE_SAVE_OFFSET,
        0x1E0,
    )


def open_retail_daycare_lady(
    emu: DeSmuME,
) -> dict[str, object]:
    """Reach std_daycare_lady through the real Route 34 door and event object."""
    script_hits: list[int] = []

    def script_started(_address: int, _size: int) -> None:
        script_hits.append(emu.memory.register_arm9.r1)

    emu.memory.register_exec(FUNC_EVENT_SET_SCRIPT, script_started)
    try:
        tap(emu, "B", 30)
        hold(emu, "UP", 24, 180)
        entrance = runtime_field_location(emu)
        require(
            entrance[:4] == (331, 0, 3, 12),
            f"retail daycare entrance differs: {entrance}",
        )
        hold(emu, "UP", 10, 20)
        hold(emu, "LEFT", 10, 20)
        hold(emu, "UP", 120, 30)
        hold(emu, "RIGHT", 10, 20)
        tap(emu, "UP", 20)
        service_tile = runtime_field_location(emu)
        require(
            service_tile == (331, 0, 3, 7, 0),
            f"retail daycare service tile differs: {service_tile}",
        )
        tap(emu, "A", 120)
    finally:
        emu.memory.register_exec(FUNC_EVENT_SET_SCRIPT, None)
    require(
        script_hits == [9501],
        f"retail daycare script boundary differs: {script_hits}",
    )
    return {
        "exterior": [TASK6_DAYCARE_MAP, -1, *TASK6_DAYCARE_EXTERIOR, 0],
        "entrance": list(entrance),
        "service_tile": list(service_tile),
        "script_id": script_hits[0],
        "event_object": {"x": 3, "z": 5, "facing": "south"},
    }


def open_retail_daycare_party_chooser(emu: DeSmuME) -> None:
    # Complete two messages, accept the default YES, complete the selection
    # prompt, and let the retail party chooser finish its fade.
    for _ in range(6):
        HEADLESS.tap_key(emu, "A", 24, 120)


def task6_daycare_cancel_evidence(
    emu: DeSmuME,
    raw: bytes,
    screenshot_path: Path,
) -> dict[str, object]:
    route = open_retail_daycare_lady(emu)
    open_retail_daycare_party_chooser(emu)
    # Walking legitimately increments deposited-owner daycare steps. Snapshot
    # at the chooser transaction boundary, immediately before retail cancel.
    before_party = wait_party_locked(emu)
    before_daycare = runtime_daycare_image(emu)
    before_pc = read_bytes(
        emu, runtime_pc_storage_address(emu), PC_SAVE_SIZE
    )
    before_metadata, before_history = runtime_history(emu)
    HEADLESS.tap_key(emu, "B", 24, 360)
    after_party = wait_party_locked(emu)
    after_daycare = runtime_daycare_image(emu)
    after_pc = read_bytes(
        emu, runtime_pc_storage_address(emu), PC_SAVE_SIZE
    )
    after_metadata, after_history = runtime_history(emu)
    require(
        after_party == before_party
        and after_daycare == before_daycare
        and after_pc == before_pc
        and after_metadata == before_metadata
        and after_history == before_history,
        "retail daycare party-chooser cancel changed canonical state",
    )
    validate_all_party_checksums(after_party)
    _, pc_base = active_pc_copy(raw)
    validate_all_boxed_checksums(raw, pc_base)
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    capture = screenshot(emu, screenshot_path.parent, screenshot_path.name)
    return {
        "label": "task6_daycare_cancel",
        "evidence_kind": "actual retail std_daycare_lady cancel",
        "route": route,
        "party_exact": True,
        "daycare_exact": True,
        "pc_exact": True,
        "history_exact": True,
        "dirty": after_metadata[4],
        "all_six_party_checksums_valid": True,
        "all_900_boxed_checksums_valid": True,
        "capture": capture,
    }


def task6_daycare_sanitize_evidence(
    emu: DeSmuME,
    raw: bytes,
    screenshot_path: Path,
) -> dict[str, object]:
    baseline_counter, before_count, before_party = PARTY.party_image(raw)
    require(before_count == 5, "daycare fixture party count differs")
    party_box = party_record(before_party, TARGET_SLOT)[:PC_MON_SIZE]
    party_pid, party_ot_id, _ = box_identity(party_box)
    deposited_box = runtime_daycare_box(emu, 0)
    deposited_pid, deposited_ot_id, _ = box_identity(deposited_box)

    route = open_retail_daycare_lady(emu)
    open_retail_daycare_party_chooser(emu)
    # Walking may increase deposited-owner steps. Pin the actual mutation
    # transaction at the chooser boundary, immediately before STORE.
    before_daycare = runtime_daycare_image(emu)
    before_pc = read_bytes(
        emu, runtime_pc_storage_address(emu), PC_SAVE_SIZE
    )
    before_metadata, before_history = runtime_history(emu)
    before_revision = struct.unpack_from("<I", before_metadata, 8)[0]
    party_index, _, party_history_before = find_history_record(
        before_history, party_pid, party_ot_id
    )
    deposited_index, _, deposited_history_before = find_history_record(
        before_history, deposited_pid, deposited_ot_id
    )
    require(
        party_history_before == TASK6_DAYCARE_PARTY_HISTORY
        and deposited_history_before == TASK6_DAYCARE_DEPOSITED_HISTORY
        and box_identity(before_daycare[:PC_MON_SIZE])[:2]
        == (deposited_pid, deposited_ot_id),
        "daycare chooser acquisition/owner state differs",
    )
    HEADLESS.tap_key(emu, "DOWN", 8, 60)
    HEADLESS.tap_key(emu, "A", 24, 90)
    HEADLESS.tap_key(emu, "A", 24, 900)
    after_party = wait_party_locked(emu)
    require(
        struct.unpack_from("<i", after_party, 4)[0] == before_count - 1,
        "retail daycare did not remove the selected party owner",
    )
    after_daycare = runtime_daycare_image(emu)
    after_deposited = after_daycare[:PC_MON_SIZE]
    after_selected = after_daycare[
        DAYCARE_MON_SIZE:DAYCARE_MON_SIZE + PC_MON_SIZE
    ]
    require(
        box_identity(after_deposited)[:2]
        == (deposited_pid, deposited_ot_id)
        and box_identity(after_selected)[:2] == (party_pid, party_ot_id),
        "retail daycare deposit changed owner identity/order",
    )
    _, deposited_moves, deposited_pp, deposited_pp_ups = (
        box_record_payload(after_deposited)
    )
    _, selected_moves, selected_pp, selected_pp_ups = (
        box_record_payload(after_selected)
    )
    require(
        deposited_moves == (57, 48, 282, 109)
        and selected_moves == (57, 48, 109, 282)
        and deposited_pp[3] == TASK6_DAYCARE_DEPOSITED_NEW_PP
        and selected_pp[3] == TASK6_DAYCARE_PARTY_NEW_PP
        and deposited_pp_ups[3] == 0
        and selected_pp_ups[3] == 0,
        "retail daycare sanitizer move/PP transaction differs",
    )
    validate_box_checksum(after_deposited, "retail deposited owner")
    validate_box_checksum(after_selected, "retail selected owner")
    require(
        after_daycare[PC_MON_SIZE:DAYCARE_MON_SIZE]
        == before_daycare[PC_MON_SIZE:DAYCARE_MON_SIZE],
        "retail sanitizer changed the existing owner's extras/steps",
    )
    after_metadata, after_history = runtime_history(emu)
    after_revision = struct.unpack_from("<I", after_metadata, 8)[0]
    new_party_index, _, party_history_after = find_history_record(
        after_history, party_pid, party_ot_id
    )
    new_deposited_index, _, deposited_history_after = find_history_record(
        after_history, deposited_pid, deposited_ot_id
    )
    require(
        new_party_index == party_index
        and new_deposited_index == deposited_index
        and party_history_after
        == party_history_before + (282,)
        and deposited_history_after
        == deposited_history_before + (109,)
        and history_identity_count(after_history, party_pid, party_ot_id) == 1
        and history_identity_count(
            after_history, deposited_pid, deposited_ot_id
        )
        == 1
        and after_revision == before_revision + 2
        and after_metadata[4] == 1,
        "retail daycare history transaction did not commit exactly once",
    )
    for index, (old_record, new_record) in enumerate(
        zip(history_records(before_history), history_records(after_history))
    ):
        if index not in (party_index, deposited_index):
            require(
                old_record == new_record,
                f"retail daycare changed unrelated history record {index}",
            )
    require(
        read_bytes(emu, runtime_pc_storage_address(emu), PC_SAVE_SIZE)
        == before_pc,
        "retail daycare changed PC storage",
    )
    validate_all_party_checksums(after_party)
    _, pc_base = active_pc_copy(raw)
    validate_all_boxed_checksums(raw, pc_base)
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    capture = screenshot(emu, screenshot_path.parent, screenshot_path.name)

    tap(emu, "A", 120)
    tap(emu, "A", 180)
    retail_save_from_field(emu, baseline_counter)
    exported = screenshot_path.with_suffix(".sav")
    exported_record = export_backup_artifact(emu, exported)
    exported = artifact_path(exported_record)
    persisted_raw = PARTY.extract_raw_save(exported)
    persisted_raw_sha256 = hashlib.sha256(persisted_raw).hexdigest()
    _, persisted_base = PARTY.active_copy(persisted_raw)
    persisted_daycare = persisted_raw[
        persisted_base + DAYCARE_SAVE_OFFSET:
        persisted_base + DAYCARE_SAVE_OFFSET + 0x1E0
    ]
    persisted_deposited = persisted_daycare[:PC_MON_SIZE]
    persisted_selected = persisted_daycare[
        DAYCARE_MON_SIZE:DAYCARE_MON_SIZE + PC_MON_SIZE
    ]
    _, _, persisted_deposited_pp, persisted_deposited_pp_ups = (
        box_record_payload(persisted_deposited)
    )
    _, _, persisted_selected_pp, persisted_selected_pp_ups = (
        box_record_payload(persisted_selected)
    )
    require(
        box_identity(persisted_deposited)[:2]
        == (deposited_pid, deposited_ot_id)
        and box_identity(persisted_selected)[:2]
        == (party_pid, party_ot_id),
        "retail daycare owners did not persist",
    )
    require(
        persisted_deposited_pp[3] == TASK6_DAYCARE_DEPOSITED_NEW_PP
        and persisted_selected_pp[3] == TASK6_DAYCARE_PARTY_NEW_PP
        and persisted_deposited_pp_ups[3] == 0
        and persisted_selected_pp_ups[3] == 0,
        "retail daycare PP/PP-Up transaction did not persist",
    )
    _, _, persisted_history = selected_persisted_history(persisted_raw)
    require(
        find_history_record(
            persisted_history, party_pid, party_ot_id
        )[2]
        == party_history_after
        and find_history_record(
            persisted_history, deposited_pid, deposited_ot_id
        )[2]
        == deposited_history_after,
        "retail daycare history did not persist",
    )
    return {
        "label": "task6_daycare_sanitize",
        "evidence_kind":
            "actual retail std_daycare_lady -> DaycareSanitizeMon -> deposit",
        "route": route,
        "party_identity": [party_pid, party_ot_id],
        "deposited_identity": [deposited_pid, deposited_ot_id],
        "party_moves": list(selected_moves),
        "deposited_moves": list(deposited_moves),
        "party_pp": list(selected_pp),
        "deposited_pp": list(deposited_pp),
        "party_pp_ups": list(selected_pp_ups),
        "deposited_pp_ups": list(deposited_pp_ups),
        "party_history": list(party_history_after),
        "deposited_history": list(deposited_history_after),
        "revision": {"before": before_revision, "after": after_revision},
        "one_record_per_identity": True,
        "unrelated_history_records_exact": True,
        "pc_exact": True,
        "all_six_party_checksums_valid": True,
        "all_900_boxed_checksums_valid": True,
        "exported_raw_save": str(exported),
        "exported_raw_sha256": persisted_raw_sha256,
        "capture": capture,
    }


def task6_daycare_reload_evidence(
    emu: DeSmuME,
    raw: bytes,
    screenshot_path: Path,
) -> dict[str, object]:
    _, count, party = PARTY.party_image(raw)
    metadata, history = runtime_history(emu)
    deposited = runtime_daycare_box(emu, 0)
    selected = runtime_daycare_box(emu, 1)
    deposited_pid, deposited_ot_id, _ = box_identity(deposited)
    selected_pid, selected_ot_id, _ = box_identity(selected)
    deposited_history = find_history_record(
        history, deposited_pid, deposited_ot_id
    )[2]
    selected_history = find_history_record(
        history, selected_pid, selected_ot_id
    )[2]
    _, _, deposited_pp, deposited_pp_ups = box_record_payload(deposited)
    _, _, selected_pp, selected_pp_ups = box_record_payload(selected)
    require(
        count == 4
        and metadata[4] == 0
        and box_record_payload(deposited)[1] == (57, 48, 282, 109)
        and box_record_payload(selected)[1] == (57, 48, 109, 282)
        and deposited_pp[3] == TASK6_DAYCARE_DEPOSITED_NEW_PP
        and selected_pp[3] == TASK6_DAYCARE_PARTY_NEW_PP
        and deposited_pp_ups[3] == 0
        and selected_pp_ups[3] == 0
        and deposited_history == TASK6_DAYCARE_DEPOSITED_HISTORY + (109,)
        and selected_history == TASK6_DAYCARE_PARTY_HISTORY + (282,)
        and history_identity_count(
            history, deposited_pid, deposited_ot_id
        )
        == 1
        and history_identity_count(history, selected_pid, selected_ot_id)
        == 1,
        "fresh daycare reload lost canonical owners/history",
    )
    validate_all_party_checksums(party)
    _, pc_base = active_pc_copy(raw)
    validate_all_boxed_checksums(raw, pc_base)
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    capture = screenshot(emu, screenshot_path.parent, screenshot_path.name)
    return {
        "label": "task6_daycare_reload",
        "evidence_kind": "fresh emulator retail-daycare save reload",
        "party_count": count,
        "deposited_identity": [deposited_pid, deposited_ot_id],
        "selected_identity": [selected_pid, selected_ot_id],
        "deposited_history": list(deposited_history),
        "selected_history": list(selected_history),
        "deposited_pp": list(deposited_pp),
        "selected_pp": list(selected_pp),
        "deposited_pp_ups": list(deposited_pp_ups),
        "selected_pp_ups": list(selected_pp_ups),
        "one_record_per_identity": True,
        "history_dirty": metadata[4],
        "all_six_party_checksums_valid": True,
        "all_900_boxed_checksums_valid": True,
        "capture": capture,
    }


def task6_pokewalker_rom_evidence(
    emu: DeSmuME,
    screenshot_path: Path,
) -> dict[str, object]:
    """Exercise the packaged task-6 Walker transaction entries on ARM9."""
    save = save_data_pointer(emu)
    metadata_address = save + SAVE_HISTORY_POINTER_OFFSET
    history_pointer = read_u32(emu, metadata_address)
    pc_storage = runtime_pc_storage_address(emu)
    box_address = runtime_box_address(emu, 0, BOX_TARGET_SLOT)
    baseline_party = runtime_party(emu)
    baseline_pc = read_bytes(emu, pc_storage, PC_SAVE_SIZE)
    baseline_metadata, baseline_history = runtime_history(emu)
    baseline_box = runtime_box_record(emu, 0, BOX_TARGET_SLOT)
    mailbox_before = read_bytes(
        emu, TASK6_POKEWALKER_MAILBOX, TASK6_POKEWALKER_MAILBOX_SIZE
    )
    require(
        mailbox_before == bytes(TASK6_POKEWALKER_MAILBOX_SIZE),
        "task-6 diagnostic mailbox is not zero/default retail-inert",
    )
    pending_box = controlled_box_record(
        baseline_box,
        ot_id_xor=0x6E6F6E65,
        moves=(33, 45, 98, 129),
        pp=(10, 10, 10, 10),
        pp_ups=(0, 0, 0, 0),
    )
    pending_identity = box_identity(pending_box)[:2]
    require(
        history_identity_count(baseline_history, *pending_identity) == 0,
        "ROM Walker pending identity already exists",
    )

    def install_history(
        image: bytes,
        *,
        revision: int,
        dirty: int = 0,
    ) -> None:
        require(len(image) == HISTORY_IMAGE_SIZE, "ROM Walker history size differs")
        write_bytes(emu, history_pointer, image)
        write_u8(emu, metadata_address + 4, dirty)
        write_u32(emu, metadata_address + 8, revision)

    def fingerprint() -> dict[str, object]:
        metadata, image = runtime_history(emu)
        return {
            "image": image,
            "record_count": struct.unpack_from("<H", image, 14)[0],
            "next_access_sequence": struct.unpack_from("<I", image, 20)[0],
            "revision": struct.unpack_from("<I", metadata, 8)[0],
            "dirty": metadata[4],
        }

    def public_fingerprint(value: dict[str, object]) -> dict[str, object]:
        image = value["image"]
        require(isinstance(image, bytes), "ROM Walker fingerprint image differs")
        return {
            "image_sha256": hashlib.sha256(image).hexdigest(),
            "record_count": value["record_count"],
            "next_access_sequence": value["next_access_sequence"],
            "revision": value["revision"],
            "dirty": value["dirty"],
        }

    invocations: list[dict[str, object]] = []
    try:
        write_bytes(emu, box_address, pending_box)
        write_bytes(
            emu,
            TASK6_POKEWALKER_MAILBOX,
            bytes(TASK6_POKEWALKER_MAILBOX_SIZE),
        )

        # Missing-identity cancellation: stage and the real packaged discard
        # boundary must leave the complete task-3 store and metadata exact.
        install_history(baseline_history, revision=0x10203040)
        missing_before = fingerprint()
        stage = invoke_packaged_mailbox_operation(
            emu,
            TASK6_POKEWALKER_OP_STAGE,
            TASK6_POKEWALKER_STAGE_ENTRY,
            boxno=0,
            slotno=BOX_TARGET_SLOT,
        )
        require(
            stage["result"] == box_address,
            "packaged Walker stage returned the wrong canonical owner",
        )
        invocations.append(stage)
        require(
            fingerprint() == missing_before,
            "packaged missing-identity stage changed task-3 state",
        )
        invocations.append(
            invoke_packaged_mailbox_operation(
                emu,
                TASK6_POKEWALKER_OP_RECOVER,
                TASK6_POKEWALKER_RECOVERY_ENTRY,
            )
        )
        missing_after = fingerprint()
        require(
            missing_after == missing_before,
            "packaged missing-identity recovery changed task-3 state",
        )

        # Full-capacity cancellation independently proves that staging cannot
        # allocate or evict the oldest record before radio success.
        full_image = bytearray(baseline_history)
        full_image[:HISTORY_FOOTER_OFFSET] = bytes(HISTORY_FOOTER_OFFSET)
        full_image[:HISTORY_HEADER_SIZE] = baseline_history[:HISTORY_HEADER_SIZE]
        struct.pack_into("<H", full_image, 14, HISTORY_RECORD_COUNT)
        struct.pack_into("<I", full_image, 20, 0x01000000)
        for index in range(HISTORY_RECORD_COUNT):
            record_offset = HISTORY_HEADER_SIZE + index * HISTORY_RECORD_SIZE
            struct.pack_into(
                "<IIIHBBH",
                full_image,
                record_offset,
                0x70000000 + index,
                0x71000000 + index,
                index + 1,
                1 + index % 493,
                1,
                1,
                1 + index % 467,
            )
        require(
            history_identity_count(bytes(full_image), *pending_identity) == 0,
            "ROM Walker full store collides with pending identity",
        )
        install_history(bytes(full_image), revision=0x50607080)
        full_before = fingerprint()
        oldest_before = history_records(full_before["image"])[0]
        unrelated_before = history_records(full_before["image"])[173]
        invocations.append(
            invoke_packaged_mailbox_operation(
                emu,
                TASK6_POKEWALKER_OP_STAGE,
                TASK6_POKEWALKER_STAGE_ENTRY,
                boxno=0,
                slotno=BOX_TARGET_SLOT,
            )
        )
        require(
            fingerprint() == full_before,
            "packaged full-capacity stage changed or evicted history",
        )
        invocations.append(
            invoke_packaged_mailbox_operation(
                emu,
                TASK6_POKEWALKER_OP_RECOVER,
                TASK6_POKEWALKER_RECOVERY_ENTRY,
            )
        )
        full_after = fingerprint()
        require(
            full_after == full_before
            and history_records(full_after["image"])[0] == oldest_before
            and history_records(full_after["image"])[173] == unrelated_before,
            "packaged full-capacity recovery changed oldest/unrelated history",
        )

        ack_evidence: dict[str, object] = {}
        for label, operation, entry, revision in (
            (
                "first",
                TASK6_POKEWALKER_OP_ACK_FIRST,
                TASK6_POKEWALKER_ACK_FIRST_ENTRY,
                0x90,
            ),
            (
                "second",
                TASK6_POKEWALKER_OP_ACK_SECOND,
                TASK6_POKEWALKER_ACK_SECOND_ENTRY,
                0x190,
            ),
        ):
            # Clear any prior pending bit through the actual recovery entry,
            # then run this ACK entry twice against an independently reset
            # missing-identity store.
            invocations.append(
                invoke_packaged_mailbox_operation(
                    emu,
                    TASK6_POKEWALKER_OP_RECOVER,
                    TASK6_POKEWALKER_RECOVERY_ENTRY,
                )
            )
            install_history(baseline_history, revision=revision)
            before = fingerprint()
            unrelated_records = history_records(before["image"])
            stage = invoke_packaged_mailbox_operation(
                emu,
                TASK6_POKEWALKER_OP_STAGE,
                TASK6_POKEWALKER_STAGE_ENTRY,
                boxno=0,
                slotno=BOX_TARGET_SLOT,
            )
            require(stage["result"] == box_address, "ACK stage owner differs")
            invocations.append(stage)
            counter_before = 0x1200
            first_call = invoke_packaged_mailbox_operation(
                emu,
                operation,
                entry,
                walker_counter_seed=counter_before,
            )
            invocations.append(first_call)
            once = fingerprint()
            counter_once = int(first_call["walker_counter_after"])
            second_call = invoke_packaged_mailbox_operation(
                emu,
                operation,
                entry,
                walker_counter_seed=counter_once,
            )
            invocations.append(second_call)
            twice = fingerprint()
            counter_twice = int(second_call["walker_counter_after"])
            once_image = once["image"]
            require(isinstance(once_image, bytes), "ACK image differs")
            new_record_index = find_history_record(
                once_image,
                *pending_identity,
            )[0]
            unrelated_records_exact = all(
                record == unrelated_records[index]
                for index, record in enumerate(history_records(once_image))
                if index != new_record_index
            )
            require(
                once["record_count"] == before["record_count"] + 1
                and once["next_access_sequence"]
                == before["next_access_sequence"] + 5
                and once["revision"] == before["revision"] + 5
                and once["dirty"] == 1
                and twice == once
                and counter_once == (counter_before + 1) & 0xFFFF
                and counter_twice == (counter_before + 2) & 0xFFFF
                and history_identity_count(once_image, *pending_identity) == 1
                and find_history_record(once_image, *pending_identity)[2]
                == (33, 45, 98, 129)
                and unrelated_records_exact,
                f"packaged {label} ACK did not consume pending exactly once: "
                f"before={public_fingerprint(before)!r}, "
                f"after_first={public_fingerprint(once)!r}, "
                f"after_second={public_fingerprint(twice)!r}, "
                f"counter={counter_before}/{counter_once}/{counter_twice}, "
                f"identity_count="
                f"{history_identity_count(once_image, *pending_identity)}, "
                f"identity_history="
                f"{find_history_record(once_image, *pending_identity)[2]!r}",
            )
            ack_evidence[label] = {
                "entry": f"0x{entry:08X}",
                "before": public_fingerprint(before),
                "after_first": public_fingerprint(once),
                "after_second": public_fingerprint(twice),
                "counter_before": counter_before,
                "counter_after_first": counter_once,
                "counter_after_second": counter_twice,
                "one_allocation": True,
                "second_revision_inert": True,
                "one_identity_record": True,
                "all_unrelated_records_exact": True,
            }

        entry_bytes = {
            f"0x{address:08X}": read_bytes(emu, address, 8).hex()
            for address in (
                TASK6_POKEWALKER_STAGE_ENTRY,
                TASK6_POKEWALKER_ACK_FIRST_ENTRY,
                TASK6_POKEWALKER_ACK_SECOND_ENTRY,
                TASK6_POKEWALKER_RECOVERY_ENTRY,
                TASK6_POKEWALKER_DIAGNOSTIC_POLL,
            )
        }
    finally:
        write_bytes(emu, pc_storage, baseline_pc)
        write_bytes(emu, history_pointer, baseline_history)
        write_bytes(emu, metadata_address, baseline_metadata)
        write_bytes(emu, TASK6_POKEWALKER_MAILBOX, mailbox_before)

    restored_metadata, restored_history = runtime_history(emu)
    require(
        runtime_party(emu) == baseline_party
        and read_bytes(emu, pc_storage, PC_SAVE_SIZE) == baseline_pc
        and restored_metadata == baseline_metadata
        and restored_history == baseline_history
        and read_bytes(
            emu,
            TASK6_POKEWALKER_MAILBOX,
            TASK6_POKEWALKER_MAILBOX_SIZE,
        )
        == mailbox_before,
        "ROM Walker diagnostic did not restore all borrowed runtime state",
    )
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    capture = screenshot(emu, screenshot_path.parent, screenshot_path.name)
    return {
        "label": "task6_pokewalker_rom",
        "evidence_kind": "ROM-executed packaged task-6 transaction boundary",
        "packaged_entries": entry_bytes,
        "invocations": invocations,
        "missing_identity_cancel": {
            "before": public_fingerprint(missing_before),
            "after": public_fingerprint(missing_after),
            "complete_store_metadata_exact": True,
        },
        "full_319_cancel": {
            "before": public_fingerprint(full_before),
            "after": public_fingerprint(full_after),
            "complete_store_metadata_exact": True,
            "oldest_record_exact": True,
            "unrelated_record_exact": True,
        },
        "ack_entries": ack_evidence,
        "named_source_retail_ack": "sub_02032644 increments u16 +0x124",
        "named_source_recovery": "ov112_021EC134 restores the canonical owner",
        "diagnostic_mailbox_restored": True,
        "zero_magic_retail_inert": True,
        "host_pc_or_register_write": False,
        "party_pc_history_restored": True,
        "task7_mode_present": False,
        "capture": capture,
    }



def run_isolated_scenario(
    rom: Path,
    raw_path: Path,
    expected_raw_sha256: str,
    name: str,
    screenshot_path: Path,
) -> dict[str, object]:
    raw = raw_path.read_bytes()
    require(
        hashlib.sha256(raw).hexdigest() == expected_raw_sha256,
        f"{name} controlled raw SHA-256 differs before emulation",
    )
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    with HEADLESS.silence_native_output(True):
        emu, imported = new_emulator(rom, raw)
        try:
            _, _, expected_party = PARTY.party_image(raw)
            party, _ = PARTY.wait_for_runtime_party(
                emu, expected_party, maximum_frames=90
            )
            require(party == expected_party, f"{name} boot party differs")
            metadata, history = runtime_history(emu)
            require(metadata[4] == 0, f"{name} did not boot clean history")
            if name == "task6_daycare_cancel":
                return task6_daycare_cancel_evidence(
                    emu, raw, screenshot_path
                )
            elif name == "task6_daycare_sanitize":
                return task6_daycare_sanitize_evidence(
                    emu, raw, screenshot_path
                )
            elif name == "task6_daycare_reload":
                return task6_daycare_reload_evidence(
                    emu, raw, screenshot_path
                )
            elif name == "task6_pokewalker_rom":
                return task6_pokewalker_rom_evidence(
                    emu, screenshot_path
                )
            elif name == "empty":
                open_summary_moves(emu, 0)
                party = wait_party_locked(emu)
                metadata, history = runtime_history(emu)
                _, moves, _, _ = record_payload(party_record(party, 0))
                touch(emu, 40, 140, 60)
                state = locate_summary_relearn_state(
                    emu, moves, owner_pos=0, minimum_candidates=0
                )
                summary_state_evidence(
                    emu, state, 2, 0, "natural empty candidate list"
                )
                require(
                    read_u16(
                        emu,
                        state + SUMMARY_STATE_CANDIDATE_COUNT_OFFSET,
                    )
                    == 0,
                    "empty mode retained candidates",
                )
                touch(emu, 220, 176, 50)
                summary_state_evidence(
                    emu, state, 0, 0, "touch empty Back"
                )
                detail = {"mode": 0, "candidate_count": 0}
            elif name == "party_fail_closed":
                require(
                    not overlay_is_active(emu, SUMMARY_RELEARN_OVERLAY_ID),
                    "party malformed fixture booted with overlay 154 active",
                )
                open_summary_info(emu, TARGET_SLOT)
                wait_overlay_active(emu, SUMMARY_RELEARN_OVERLAY_ID, True)
                baseline_party = runtime_party(emu)
                baseline_pc = read_bytes(
                    emu, runtime_pc_storage_address(emu), PC_SAVE_SIZE
                )
                baseline_metadata, baseline_history = runtime_history(emu)
                state = locate_inactive_summary_state(
                    emu, page_mode=None
                )
                summary = state - SUMMARY_STATE_RETAIL_SIZE
                owner = read_u32(
                    emu, summary + SUMMARY_BASE_POINTER_OFFSET
                )
                baseline_owner = read_bytes(
                    emu, owner, SUMMARY_OWNER_ARGS_SIZE
                )
                require(
                    read_bytes(emu, state, SUMMARY_STATE_EXTENSION_SIZE)
                    == bytes(SUMMARY_STATE_EXTENSION_SIZE),
                    "party malformed fixture did not begin with fresh state",
                )
                party_address = save_data_pointer(emu) + PARTY_OFFSET
                target_address = (
                    party_address + 8 + TARGET_SLOT * 0xEC
                )
                target_box = party_record(
                    baseline_party, TARGET_SLOT
                )[:PC_MON_SIZE]
                empty_party_box = party_record(
                    baseline_party, 5
                )[:PC_MON_SIZE]
                require(
                    box_identity(empty_party_box)[2] == 0,
                    "party fixture slot 5 is not an actual empty record",
                )
                invalid_boxes = {
                    "empty_record": empty_party_box,
                    "egg": authenticated_box_variant(
                        target_box, is_egg=True
                    ),
                    "checksum_failure": checksum_failed_box_variant(
                        target_box
                    ),
                    "species_1076": authenticated_box_variant(
                        target_box, species=1076
                    ),
                    "tentacool_form_31": authenticated_box_variant(
                        target_box, form=31
                    ),
                }
                probes: list[tuple[str, str, int | bytes]] = [
                    ("count_negative_one", "count", 0xFFFFFFFF),
                    ("count_zero", "count", 0),
                    ("count_seven", "count", 7),
                    ("limit_zero", "limit", 0),
                    ("limit_seven", "limit", 7),
                    ("position_six", "position", 6),
                    ("data_type_zero", "data_type", 0),
                    *(
                        (label, "box", box)
                        for label, box in invalid_boxes.items()
                    ),
                ]
                fixture_results: list[dict[str, object]] = []
                for label, kind, value in probes:
                    def inject_probe() -> None:
                        if kind == "count":
                            write_u32(
                                emu, party_address + 4, int(value)
                            )
                        elif kind == "limit":
                            write_u8(
                                emu,
                                owner + SUMMARY_BASE_LIMIT_OFFSET,
                                int(value),
                            )
                        elif kind == "position":
                            write_u8(
                                emu,
                                owner + SUMMARY_BASE_POS_OFFSET,
                                int(value),
                            )
                        elif kind == "data_type":
                            write_u8(
                                emu,
                                owner + SUMMARY_BASE_DATA_TYPE_OFFSET,
                                int(value),
                            )
                        else:
                            write_bytes(
                                emu, target_address, bytes(value)
                            )

                    def capture_probe() -> tuple[
                        bytes,
                        bytes,
                        bytes,
                        bytes,
                        bytes,
                        int,
                        int,
                    ]:
                        captured_metadata, captured_history = (
                            runtime_history(emu)
                        )
                        return (
                            runtime_party(emu),
                            read_bytes(
                                emu,
                                runtime_pc_storage_address(emu),
                                PC_SAVE_SIZE,
                            ),
                            read_bytes(
                                emu, owner, SUMMARY_OWNER_ARGS_SIZE
                            ),
                            captured_metadata,
                            captured_history,
                            read_u8(
                                emu,
                                summary + SUMMARY_PAGE_MODE_OFFSET,
                            ),
                            read_u8(
                                emu,
                                summary + SUMMARY_TRANSITION_OFFSET,
                            ),
                        )

                    captured_probe = navigate_to_moves_with_injection(
                        emu,
                        summary,
                        inject_probe,
                        capture_probe,
                        f"party {label}",
                    )
                    require(
                        isinstance(captured_probe, tuple)
                        and len(captured_probe) == 7,
                        f"party {label} lacks a pre-frame fixture snapshot",
                    )
                    (
                        malformed_party,
                        malformed_pc,
                        malformed_owner,
                        malformed_metadata,
                        malformed_history,
                        malformed_page,
                        malformed_transition,
                    ) = captured_probe
                    require(
                        malformed_metadata == baseline_metadata
                        and malformed_history == baseline_history,
                        f"party {label} changed history during injection",
                    )
                    require(
                        read_u8(
                            emu, summary + SUMMARY_PAGE_MODE_OFFSET
                        )
                        == 1,
                        f"{label} did not reach the real Moves page",
                    )
                    if kind != "box":
                        tap(emu, "LEFT", 12)
                        assert_malformed_navigation_consumed(
                            emu,
                            summary,
                            expected_page=malformed_page,
                            expected_transition=malformed_transition,
                            label=f"party {label} LEFT",
                        )
                        tap(emu, "RIGHT", 12)
                        assert_malformed_navigation_consumed(
                            emu,
                            summary,
                            expected_page=malformed_page,
                            expected_transition=malformed_transition,
                            label=f"party {label} RIGHT",
                        )
                        touch(emu, 224, 92, 12)
                        assert_malformed_navigation_consumed(
                            emu,
                            summary,
                            expected_page=malformed_page,
                            expected_transition=malformed_transition,
                            label=f"party {label} switch touch",
                        )
                    tap(emu, "X", 16)
                    touch(emu, 40, 140, 24)
                    fixture_results.append(
                        assert_fail_closed_fixture(
                            emu,
                            state,
                            label=f"party {label}",
                            expected_party=malformed_party,
                            expected_pc=malformed_pc,
                            expected_owner_args=malformed_owner,
                            expected_metadata=malformed_metadata,
                            expected_history=malformed_history,
                        )
                    )
                    fixture_results[-1]["expected_snapshot_phase"] = (
                        "immediate_post_injection_pre_frame"
                    )

                    # Restore the exact retail owners before vanilla page/exit
                    # handling sees the next controlled malformed fixture.
                    write_bytes(emu, party_address, baseline_party)
                    write_bytes(emu, owner, baseline_owner)
                    tap(emu, "LEFT", 80)
                    require(
                        read_u8(
                            emu, summary + SUMMARY_PAGE_MODE_OFFSET
                        )
                        != 1,
                        f"{label} did not return to Info",
                    )
                    require(
                        runtime_party(emu) == baseline_party
                        and read_bytes(
                            emu,
                            runtime_pc_storage_address(emu),
                            PC_SAVE_SIZE,
                        )
                        == baseline_pc
                        and runtime_history(emu)
                        == (baseline_metadata, baseline_history),
                        f"{label} restoration changed persistent owners",
                    )
                post_prompt_results: list[dict[str, object]] = []
                for label, invalid_box, activation in (
                    (
                        "post_prompt_species_1076_key",
                        invalid_boxes["species_1076"],
                        "key",
                    ),
                    (
                        "post_prompt_tentacool_form_31_touch",
                        invalid_boxes["tentacool_form_31"],
                        "touch",
                    ),
                ):
                    tap(emu, "RIGHT", 80)
                    expected_prompt = bytearray(
                        SUMMARY_STATE_EXTENSION_SIZE
                    )
                    expected_prompt[
                        SUMMARY_STATE_PROMPT_VISIBLE_OFFSET
                    ] = 1
                    require(
                        read_u8(
                            emu, summary + SUMMARY_PAGE_MODE_OFFSET
                        )
                        == 1
                        and read_bytes(
                            emu, state, SUMMARY_STATE_EXTENSION_SIZE
                        )
                        == bytes(expected_prompt),
                        f"party {label} did not display a clean prompt",
                    )
                    write_bytes(emu, target_address, invalid_box)
                    malformed_party = runtime_party(emu)
                    malformed_pc = read_bytes(
                        emu,
                        runtime_pc_storage_address(emu),
                        PC_SAVE_SIZE,
                    )
                    malformed_owner = read_bytes(
                        emu, owner, SUMMARY_OWNER_ARGS_SIZE
                    )
                    malformed_metadata, malformed_history = (
                        runtime_history(emu)
                    )
                    if activation == "key":
                        tap(emu, "X", 24)
                    else:
                        touch(emu, 40, 140, 24)
                    evidence = assert_fail_closed_fixture(
                        emu,
                        state,
                        label=f"party {label}",
                        expected_party=malformed_party,
                        expected_pc=malformed_pc,
                        expected_owner_args=malformed_owner,
                        expected_metadata=malformed_metadata,
                        expected_history=malformed_history,
                    )
                    evidence.update(
                        {
                            "injection_phase":
                                "after_prompt_before_activation",
                            "activation": activation,
                            "expected_snapshot_phase":
                                "immediate_post_injection_pre_frame",
                        }
                    )
                    post_prompt_results.append(evidence)
                    write_bytes(emu, party_address, baseline_party)
                    write_bytes(emu, owner, baseline_owner)
                    tap(emu, "LEFT", 80)
                    require(
                        read_u8(
                            emu, summary + SUMMARY_PAGE_MODE_OFFSET
                        )
                        != 1
                        and runtime_party(emu) == baseline_party
                        and read_bytes(
                            emu,
                            runtime_pc_storage_address(emu),
                            PC_SAVE_SIZE,
                        )
                        == baseline_pc
                        and runtime_history(emu)
                        == (baseline_metadata, baseline_history),
                        f"party {label} restoration changed owners",
                    )
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                screenshot(emu, screenshot_path.parent, screenshot_path.name)
                tap(emu, "B", 40)
                wait_overlay_active(
                    emu, SUMMARY_RELEARN_OVERLAY_ID, False
                )
                return {
                    "label": name,
                    "actual_party_summary_info_to_moves": True,
                    "fixture_count": len(fixture_results),
                    "fixtures": fixture_results,
                    "post_prompt_fixture_count":
                        len(post_prompt_results),
                    "post_prompt_fixtures": post_prompt_results,
                    "valid_zero_candidate_kept_separate": True,
                    "overlay_unloaded": True,
                }
            elif name == "pc_fail_closed":
                require(
                    not overlay_is_active(emu, SUMMARY_RELEARN_OVERLAY_ID),
                    "PC malformed fixture booted with overlay 154 active",
                )
                open_retail_pc_move_ui(emu, terminal_boot=True)
                touch(emu, 16, 56, 60)
                touch(emu, 210, 76, 180)
                wait_overlay_active(emu, SUMMARY_RELEARN_OVERLAY_ID, True)
                target_box = runtime_box_record(
                    emu, 0, BOX_TARGET_SLOT
                )
                empty_pc_box = runtime_box_record(emu, 0, 2)
                require(
                    box_identity(empty_pc_box)[2] == 0,
                    "PC fixture slot 2 is not an actual empty record",
                )
                target_moves = box_record_payload(target_box)[1]
                state = locate_inactive_summary_state(
                    emu,
                    moves=target_moves,
                    owner_pos=BOX_TARGET_SLOT,
                    data_type=2,
                    page_mode=None,
                )
                summary = state - SUMMARY_STATE_RETAIL_SIZE
                owner = read_u32(
                    emu, summary + SUMMARY_BASE_POINTER_OFFSET
                )
                baseline_owner = read_bytes(
                    emu, owner, SUMMARY_OWNER_ARGS_SIZE
                )
                baseline_party = runtime_party(emu)
                baseline_pc = read_bytes(
                    emu, runtime_pc_storage_address(emu), PC_SAVE_SIZE
                )
                baseline_metadata, baseline_history = runtime_history(emu)
                require(
                    read_bytes(emu, state, SUMMARY_STATE_EXTENSION_SIZE)
                    == bytes(SUMMARY_STATE_EXTENSION_SIZE),
                    "PC malformed fixture did not begin with fresh state",
                )
                target_address = runtime_box_address(
                    emu, 0, BOX_TARGET_SLOT
                )
                invalid_boxes = {
                    "empty_record": empty_pc_box,
                    "egg": authenticated_box_variant(
                        target_box, is_egg=True
                    ),
                    "checksum_failure": checksum_failed_box_variant(
                        target_box
                    ),
                    "species_1076": authenticated_box_variant(
                        target_box, species=1076
                    ),
                    "tentacool_form_31": authenticated_box_variant(
                        target_box, form=31
                    ),
                }
                probes = [
                    ("data_type_zero", "data_type", 0),
                    ("non_pc_box_limit_29", "limit", 29),
                    ("position_30", "position", 30),
                    *(
                        (label, "box", box)
                        for label, box in invalid_boxes.items()
                    ),
                ]
                fixture_results = []
                for label, kind, value in probes:
                    def inject_probe() -> None:
                        if kind == "data_type":
                            write_u8(
                                emu,
                                owner + SUMMARY_BASE_DATA_TYPE_OFFSET,
                                int(value),
                            )
                        elif kind == "limit":
                            write_u8(
                                emu,
                                owner + SUMMARY_BASE_LIMIT_OFFSET,
                                int(value),
                            )
                        elif kind == "position":
                            write_u8(
                                emu,
                                owner + SUMMARY_BASE_POS_OFFSET,
                                int(value),
                            )
                        else:
                            write_bytes(
                                emu, target_address, bytes(value)
                            )

                    def capture_probe() -> tuple[
                        bytes,
                        bytes,
                        bytes,
                        bytes,
                        bytes,
                        int,
                        int,
                    ]:
                        captured_metadata, captured_history = (
                            runtime_history(emu)
                        )
                        return (
                            runtime_party(emu),
                            read_bytes(
                                emu,
                                runtime_pc_storage_address(emu),
                                PC_SAVE_SIZE,
                            ),
                            read_bytes(
                                emu, owner, SUMMARY_OWNER_ARGS_SIZE
                            ),
                            captured_metadata,
                            captured_history,
                            read_u8(
                                emu,
                                summary + SUMMARY_PAGE_MODE_OFFSET,
                            ),
                            read_u8(
                                emu,
                                summary + SUMMARY_TRANSITION_OFFSET,
                            ),
                        )

                    if kind == "box":
                        captured_probe = navigate_to_moves_with_injection(
                            emu,
                            summary,
                            inject_probe,
                            capture_probe,
                            f"PC {label}",
                        )
                    else:
                        # Retail transition code resolves the current box
                        # before the hooked main-state callback. Inject owner
                        # corruption only after that real transition is
                        # stable, then snapshot before the first guarded frame.
                        tap(emu, "RIGHT", 80)
                        require(
                            read_u8(
                                emu,
                                summary + SUMMARY_PAGE_MODE_OFFSET,
                            )
                            == 1
                            and read_u8(
                                emu,
                                summary + SUMMARY_TRANSITION_OFFSET,
                            )
                            & 0xF0
                            == 0,
                            f"PC {label} did not reach stable Moves",
                        )
                        inject_probe()
                        captured_probe = capture_probe()
                    require(
                        isinstance(captured_probe, tuple)
                        and len(captured_probe) == 7,
                        f"PC {label} lacks a pre-frame fixture snapshot",
                    )
                    (
                        malformed_party,
                        malformed_pc,
                        malformed_owner,
                        malformed_metadata,
                        malformed_history,
                        malformed_page,
                        malformed_transition,
                    ) = captured_probe
                    require(
                        malformed_metadata == baseline_metadata
                        and malformed_history == baseline_history,
                        f"PC {label} changed history during injection",
                    )
                    require(
                        read_u8(
                            emu, summary + SUMMARY_PAGE_MODE_OFFSET
                        )
                        == 1,
                        f"PC {label} did not reach the real Moves page",
                    )
                    if kind != "box":
                        tap(emu, "LEFT", 12)
                        assert_malformed_navigation_consumed(
                            emu,
                            summary,
                            expected_page=malformed_page,
                            expected_transition=malformed_transition,
                            label=f"PC {label} LEFT",
                        )
                        tap(emu, "RIGHT", 12)
                        assert_malformed_navigation_consumed(
                            emu,
                            summary,
                            expected_page=malformed_page,
                            expected_transition=malformed_transition,
                            label=f"PC {label} RIGHT",
                        )
                        touch(emu, 215, 115, 12)
                        assert_malformed_navigation_consumed(
                            emu,
                            summary,
                            expected_page=malformed_page,
                            expected_transition=malformed_transition,
                            label=f"PC {label} switch touch",
                        )
                    tap(emu, "X", 16)
                    touch(emu, 40, 140, 24)
                    fixture_results.append(
                        assert_fail_closed_fixture(
                            emu,
                            state,
                            label=f"PC {label}",
                            expected_party=malformed_party,
                            expected_pc=malformed_pc,
                            expected_owner_args=malformed_owner,
                            expected_metadata=malformed_metadata,
                            expected_history=malformed_history,
                        )
                    )
                    fixture_results[-1]["expected_snapshot_phase"] = (
                        "immediate_post_injection_pre_frame"
                    )
                    write_bytes(
                        emu,
                        runtime_pc_storage_address(emu),
                        baseline_pc,
                    )
                    write_bytes(emu, owner, baseline_owner)
                    tap(emu, "LEFT", 80)
                    require(
                        read_u8(
                            emu, summary + SUMMARY_PAGE_MODE_OFFSET
                        )
                        != 1,
                        f"PC {label} did not return to Info",
                    )
                    require(
                        runtime_party(emu) == baseline_party
                        and runtime_history(emu)
                        == (baseline_metadata, baseline_history),
                        f"PC {label} restoration changed persistent owners",
                    )
                owner_probe_hashes = {
                    evidence["pc_sha256"]
                    for evidence in fixture_results[:3]
                }
                require(
                    len(owner_probe_hashes) == 1,
                    "PC position_30 pre-frame storage hash differs from "
                    "owner-only probes",
                )
                post_prompt_results: list[dict[str, object]] = []
                for label, invalid_box, activation in (
                    (
                        "post_prompt_species_1076_key",
                        invalid_boxes["species_1076"],
                        "key",
                    ),
                    (
                        "post_prompt_tentacool_form_31_touch",
                        invalid_boxes["tentacool_form_31"],
                        "touch",
                    ),
                ):
                    tap(emu, "RIGHT", 80)
                    expected_prompt = bytearray(
                        SUMMARY_STATE_EXTENSION_SIZE
                    )
                    expected_prompt[
                        SUMMARY_STATE_PROMPT_VISIBLE_OFFSET
                    ] = 1
                    require(
                        read_u8(
                            emu, summary + SUMMARY_PAGE_MODE_OFFSET
                        )
                        == 1
                        and read_bytes(
                            emu, state, SUMMARY_STATE_EXTENSION_SIZE
                        )
                        == bytes(expected_prompt),
                        f"PC {label} did not display a clean prompt",
                    )
                    write_bytes(emu, target_address, invalid_box)
                    malformed_party = runtime_party(emu)
                    malformed_pc = read_bytes(
                        emu,
                        runtime_pc_storage_address(emu),
                        PC_SAVE_SIZE,
                    )
                    malformed_owner = read_bytes(
                        emu, owner, SUMMARY_OWNER_ARGS_SIZE
                    )
                    malformed_metadata, malformed_history = (
                        runtime_history(emu)
                    )
                    if activation == "key":
                        tap(emu, "X", 24)
                    else:
                        touch(emu, 40, 140, 24)
                    evidence = assert_fail_closed_fixture(
                        emu,
                        state,
                        label=f"PC {label}",
                        expected_party=malformed_party,
                        expected_pc=malformed_pc,
                        expected_owner_args=malformed_owner,
                        expected_metadata=malformed_metadata,
                        expected_history=malformed_history,
                    )
                    evidence.update(
                        {
                            "injection_phase":
                                "after_prompt_before_activation",
                            "activation": activation,
                            "expected_snapshot_phase":
                                "immediate_post_injection_pre_frame",
                        }
                    )
                    post_prompt_results.append(evidence)
                    write_bytes(
                        emu,
                        runtime_pc_storage_address(emu),
                        baseline_pc,
                    )
                    write_bytes(emu, owner, baseline_owner)
                    tap(emu, "LEFT", 80)
                    require(
                        read_u8(
                            emu, summary + SUMMARY_PAGE_MODE_OFFSET
                        )
                        != 1
                        and runtime_party(emu) == baseline_party
                        and read_bytes(
                            emu,
                            runtime_pc_storage_address(emu),
                            PC_SAVE_SIZE,
                        )
                        == baseline_pc
                        and runtime_history(emu)
                        == (baseline_metadata, baseline_history),
                        f"PC {label} restoration changed owners",
                    )
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                screenshot(emu, screenshot_path.parent, screenshot_path.name)
                tap(emu, "B", 40)
                wait_overlay_active(
                    emu, SUMMARY_RELEARN_OVERLAY_ID, False
                )
                require(
                    read_bytes(
                        emu,
                        runtime_pc_storage_address(emu),
                        PC_SAVE_SIZE,
                    )
                    == baseline_pc,
                    "PC malformed fixture exit changed storage",
                )
                return {
                    "label": name,
                    "actual_terminal_pc_summary_info_to_moves": True,
                    "fixture_count": len(fixture_results),
                    "fixtures": fixture_results,
                    "pre_frame_owner_probe_pc_sha256":
                        next(iter(owner_probe_hashes)),
                    "position_30_hash_matches_owner_only_probes": True,
                    "post_prompt_fixture_count":
                        len(post_prompt_results),
                    "post_prompt_fixtures": post_prompt_results,
                    "overlay_unloaded": True,
                }
            elif name == "keys":
                open_summary_moves(emu, TARGET_SLOT)
                party, _ = PARTY.wait_for_runtime_party(
                    emu, expected_party, maximum_frames=90
                )
                metadata, history = runtime_history(emu)
                inactive = locate_inactive_summary_state(emu)
                transitions: list[dict[str, object]] = []

                tap(emu, "X", 12)
                state = locate_summary_relearn_state(emu)
                transitions.append(
                    summary_state_evidence(
                        emu, state, 1, 0, "key X entry"
                    )
                )
                initial = assert_candidate_viewport(
                    emu, state, 0, 0, "key X candidate list"
                )
                require(
                    initial["candidates"] == CONTROLLED_CANDIDATES,
                    "key-only candidate order differs",
                )
                assert_cancel_exact(
                    emu, party, metadata, history, "key X entry"
                )

                tap(emu, "A", 12)
                transitions.append(
                    summary_state_evidence(
                        emu, state, 3, 0, "key A list to slot"
                    )
                )
                assert_prospective_slot(
                    emu, state, 0, "key A initial slot preview"
                )
                tap(emu, "B", 12)
                transitions.append(
                    summary_state_evidence(
                        emu, state, 1, 0, "key B slot to list"
                    )
                )
                assert_cancel_exact(
                    emu, party, metadata, history, "key B slot cancel"
                )

                tap(emu, "A", 12)
                for selected in (1, 2, 3):
                    tap(emu, "DOWN", 12)
                    assert_prospective_slot(
                        emu,
                        state,
                        selected,
                        f"key DOWN slot {selected}",
                    )
                tap(emu, "A", 12)
                transitions.append(
                    summary_state_evidence(
                        emu, state, 4, 0, "key A slot to confirmation"
                    )
                )
                tap(emu, "B", 12)
                transitions.append(
                    summary_state_evidence(
                        emu, state, 3, 0, "key B confirmation to slot"
                    )
                )
                assert_cancel_exact(
                    emu, party, metadata, history, "key B confirmation cancel"
                )

                tap(emu, "B", 12)
                transitions.append(
                    summary_state_evidence(
                        emu, state, 1, 0, "key B slot to list again"
                    )
                )
                tap(emu, "A", 12)
                for _ in range(3):
                    tap(emu, "DOWN", 12)
                tap(emu, "A", 12)
                transitions.append(
                    summary_state_evidence(
                        emu, state, 4, 0, "key A confirmation before success"
                    )
                )
                assert_cancel_exact(
                    emu, party, metadata, history, "key confirmation pending"
                )
                tap(emu, "A", 20)
                transitions.append(
                    summary_state_evidence(
                        emu, state, 6, 1, "key A confirmed success"
                    )
                )
                changed_party = wait_party_locked(emu)
                _, changed_moves, changed_pp, changed_pp_ups = record_payload(
                    party_record(changed_party, TARGET_SLOT)
                )
                require(
                    changed_moves == (57, 48, 352, TARGET_MOVE)
                    and changed_pp[TARGET_REPLACEMENT_SLOT] == 8
                    and changed_pp_ups[TARGET_REPLACEMENT_SLOT] == 0,
                    "key-only confirmed replacement differs",
                )
                changed_metadata, changed_history = runtime_history(emu)
                require(
                    changed_metadata[4] == 1
                    and changed_history != history,
                    "key-only success did not update history",
                )
                tap(emu, "B", 20)
                transitions.append(
                    summary_state_evidence(
                        emu, state, 0, 1, "key B dismisses success"
                    )
                )
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                screenshot(emu, screenshot_path.parent, screenshot_path.name)
                return {
                    "label": name,
                    "entry_state": f"0x{inactive:08X}",
                    "transitions": transitions,
                    "candidate_order": list(initial["candidates"]),
                    "cancel_party_exact": True,
                    "cancel_history_exact": True,
                    "confirmed_moves": list(changed_moves),
                    "confirmed_pp": list(changed_pp),
                    "confirmed_pp_ups": list(changed_pp_ups),
                    "history_dirty_after_confirm": changed_metadata[4],
                }
            elif name == "party_switch":
                open_summary_moves(emu, TARGET_SLOT)
                party, _ = PARTY.wait_for_runtime_party(
                    emu, expected_party, maximum_frames=90
                )
                metadata, history = runtime_history(emu)
                tap(emu, "X", 20)
                state = locate_summary_relearn_state(emu)
                initial = candidate_state(emu, state)
                original_owner_pokemon = read_u32(
                    emu, state + SUMMARY_STATE_OWNER_POKEMON_OFFSET
                )
                switches: list[dict[str, object]] = []

                # The retail party icon hitboxes are actions 4..9. Slot 3 is
                # the right icon in the middle row and has no candidates.
                touch(emu, 224, 92, 30)
                switched = wait_summary_identity(
                    emu, state, expected_pos=3, expected_mode=2
                )
                switched_candidates = candidate_state(emu, state)
                require(
                    read_u32(
                        emu,
                        state + SUMMARY_STATE_OWNER_POKEMON_OFFSET,
                    )
                    != original_owner_pokemon,
                    "party list switch retained the old BoxPokemon owner",
                )
                require(
                    switched_candidates["candidates"] == (),
                    "party list switch did not rebuild the peer empty state",
                )
                switches.append({"from_mode": 1, **switched})
                assert_cancel_exact(
                    emu,
                    party,
                    metadata,
                    history,
                    "party list real switch",
                )

                # Slot 2 is the left icon in the middle retail party row.
                touch(emu, 184, 84, 30)
                switched = wait_summary_identity(
                    emu, state, expected_pos=TARGET_SLOT, expected_mode=1
                )
                require(
                    candidate_state(emu, state)["candidates"]
                    == initial["candidates"],
                    "party slot-state switch did not rebuild target candidates",
                )
                switches.append({"from_mode": 2, **switched})
                assert_cancel_exact(
                    emu,
                    party,
                    metadata,
                    history,
                    "party empty-state real switch",
                )

                tap(emu, "A", 12)
                require(
                    read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET) == 3,
                    "party target did not enter slot mode",
                )
                touch(emu, 224, 92, 30)
                switched = wait_summary_identity(
                    emu, state, expected_pos=3, expected_mode=2
                )
                require(
                    candidate_state(emu, state)["candidates"] == (),
                    "party slot-state switch retained target candidates",
                )
                switches.append({"from_mode": 3, **switched})
                assert_cancel_exact(
                    emu,
                    party,
                    metadata,
                    history,
                    "party slot real switch",
                )

                touch(emu, 184, 84, 30)
                switched = wait_summary_identity(
                    emu, state, expected_pos=TARGET_SLOT, expected_mode=1
                )
                require(
                    candidate_state(emu, state)["candidates"]
                    == initial["candidates"],
                    "party empty-state return did not rebuild target",
                )
                switches.append({"from_mode": 2, **switched})
                assert_cancel_exact(
                    emu,
                    party,
                    metadata,
                    history,
                    "party empty-state return",
                )

                tap(emu, "A", 12)
                for _ in range(3):
                    tap(emu, "DOWN", 8)
                tap(emu, "A", 12)
                require(
                    read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET) == 4,
                    "party target did not enter confirmation mode",
                )
                touch(emu, 224, 92, 30)
                switched = wait_summary_identity(
                    emu, state, expected_pos=3, expected_mode=2
                )
                require(
                    candidate_state(emu, state)["candidates"] == (),
                    "party confirmation-state switch did not rebuild peer",
                )
                switches.append({"from_mode": 4, **switched})
                assert_cancel_exact(
                    emu,
                    party,
                    metadata,
                    history,
                    "party confirmation real switch",
                )

                # Return to the target, select Surf in slot 0, and exercise a
                # real party-icon switch out of the HM-blocked modal.
                touch(emu, 184, 84, 30)
                switched = wait_summary_identity(
                    emu, state, expected_pos=TARGET_SLOT, expected_mode=1
                )
                require(
                    candidate_state(emu, state)["candidates"]
                    == initial["candidates"],
                    "party confirmation return did not rebuild target",
                )
                switches.append({"from_mode": 2, **switched})
                tap(emu, "A", 12)
                tap(emu, "A", 12)
                require(
                    read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET) == 5,
                    "party target did not enter HM-blocked mode",
                )
                hm_party = wait_party_locked(emu)
                hm_metadata, hm_history = runtime_history(emu)
                require(
                    hm_party == party
                    and hm_metadata == metadata
                    and hm_history == history,
                    "party HM block changed data before switching",
                )
                touch(emu, 224, 92, 30)
                switched = wait_summary_identity(
                    emu, state, expected_pos=3, expected_mode=2
                )
                require(
                    candidate_state(emu, state)["candidates"] == (),
                    "party HM-state switch retained target candidates",
                )
                switches.append({"from_mode": 5, **switched})
                assert_cancel_exact(
                    emu,
                    party,
                    metadata,
                    history,
                    "party HM-blocked real switch",
                )

                # Commit on the target, then use the actual party icons while
                # the success modal is visible. The commit must stay solely on
                # the old identity and remain visible when that identity
                # returns.
                touch(emu, 184, 84, 30)
                switched = wait_summary_identity(
                    emu, state, expected_pos=TARGET_SLOT, expected_mode=1
                )
                require(
                    candidate_state(emu, state)["candidates"]
                    == initial["candidates"],
                    "party HM return did not rebuild target candidates",
                )
                switches.append({"from_mode": 2, **switched})
                tap(emu, "A", 12)
                for _ in range(3):
                    tap(emu, "DOWN", 8)
                tap(emu, "A", 12)
                require(
                    read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET) == 4,
                    "party target did not re-enter confirmation mode",
                )
                tap(emu, "A", 20)
                require(
                    read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET) == 6,
                    "party target did not enter success mode",
                )
                committed_party = wait_party_locked(emu)
                committed_metadata, committed_history = runtime_history(emu)
                _, committed_moves, committed_pp, committed_pp_ups = (
                    record_payload(
                        party_record(committed_party, TARGET_SLOT)
                    )
                )
                require(
                    committed_moves
                    == (57, 48, 352, TARGET_MOVE)
                    and committed_pp[TARGET_REPLACEMENT_SLOT] == 8
                    and committed_pp_ups[TARGET_REPLACEMENT_SLOT] == 0,
                    "party success committed the wrong move/PP state",
                )
                for party_slot in range(6):
                    if party_slot != TARGET_SLOT:
                        require(
                            party_record(committed_party, party_slot)
                            == party_record(party, party_slot),
                            f"party success changed peer slot {party_slot}",
                        )
                target_pid, target_ot_id, _ = box_identity(
                    party_record(party, TARGET_SLOT)[:PC_MON_SIZE]
                )
                old_history_index, _, old_history_moves = (
                    find_history_record(history, target_pid, target_ot_id)
                )
                new_history_index, _, new_history_moves = (
                    find_history_record(
                        committed_history, target_pid, target_ot_id
                    )
                )
                require(
                    committed_metadata[4] == 1
                    and new_history_index == old_history_index
                    and new_history_moves[:len(old_history_moves)]
                    == old_history_moves
                    and new_history_moves.count(TARGET_MOVE) == 1,
                    "party success history identity/order differs",
                )
                for history_slot, (old_record, new_record) in enumerate(
                    zip(
                        history_records(history),
                        history_records(committed_history),
                    )
                ):
                    if history_slot != old_history_index:
                        require(
                            old_record == new_record,
                            "party success changed a peer history record",
                        )
                touch(emu, 224, 92, 30)
                switched = wait_summary_identity(
                    emu, state, expected_pos=3, expected_mode=2
                )
                switches.append({"from_mode": 6, **switched})
                require(
                    candidate_state(emu, state)["candidates"] == ()
                    and wait_party_locked(emu) == committed_party
                    and runtime_history(emu)
                    == (committed_metadata, committed_history),
                    "party success switch contaminated the peer or commit",
                )
                touch(emu, 184, 84, 30)
                switched = wait_summary_identity(
                    emu, state, expected_pos=TARGET_SLOT, expected_mode=1
                )
                switches.append({"from_mode": 2, **switched})
                require(
                    candidate_state(emu, state)["candidates"]
                    == PERSISTED_CANDIDATES
                    and wait_party_locked(emu) == committed_party
                    and runtime_history(emu)
                    == (committed_metadata, committed_history),
                    "party success return lost committed identity candidates",
                )
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                screenshot(emu, screenshot_path.parent, screenshot_path.name)
                return {
                    "label": name,
                    "switches": switches,
                    "initial_candidates": list(initial["candidates"]),
                    "peer_candidates": list(
                        switched_candidates["candidates"]
                    ),
                    "old_transactions_cancelled_exact": True,
                    "hm_switch_party_history_exact": True,
                    "success_target_moves": list(committed_moves),
                    "success_target_pp": list(committed_pp),
                    "success_target_pp_ups": list(committed_pp_ups),
                    "success_peer_exact": True,
                    "success_history_record_index": new_history_index,
                    "success_history_move_count": new_history_moves.count(
                        TARGET_MOVE
                    ),
                    "success_return_candidates": list(
                        candidate_state(emu, state)["candidates"]
                    ),
                    "dirty": committed_metadata[4],
                }
            elif name == "center_bootstrap":
                baseline_counter, _ = PARTY.active_copy(raw)
                for key, frames in (
                    ("LEFT", 90),
                    ("DOWN", 150),
                    ("RIGHT", 60),
                    ("DOWN", 100),
                    ("LEFT", 140),
                    ("UP", 60),
                    ("LEFT", 90),
                    ("UP", 140),
                ):
                    hold(emu, key, frames, 12)
                HEADLESS.cycle(emu, 300)
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                screenshot(emu, screenshot_path.parent, screenshot_path.name)
                retail_save_from_field(emu, baseline_counter)
                exported = screenshot_path.with_suffix(".sav")
                exported_record = export_backup_artifact(emu, exported)
                exported = artifact_path(exported_record)
                saved_raw = PARTY.extract_raw_save(exported)
                saved_counter, saved_base = PARTY.active_copy(saved_raw)
                location = struct.unpack_from(
                    "<5i",
                    saved_raw,
                    saved_base + LOCAL_FIELD_DATA_OFFSET,
                )
                require(
                    location[:4] == (69, -1, 8, 19),
                    f"retail Center bootstrap location differs: {location}",
                )
                return {
                    "label": name,
                    "retail_save": True,
                    "location": list(location),
                    "generation": saved_counter,
                    "normal_copies_authenticated": len(
                        PARTY.valid_normal_copies(saved_raw)
                    ),
                    "exported_raw_save": str(exported),
                    "capture": str(screenshot_path),
                }
            elif name == "terminal_bootstrap":
                baseline_counter, _ = PARTY.active_copy(raw)
                # T21PC0101's gentleman stays on y=16 at x=10..12. Keep the
                # entire north leg on the fixed x=8 entrance aisle, then move
                # east only after reaching the collision-free terminal row.
                for key, frames in (
                    ("UP", 90),
                    ("RIGHT", 45),
                ):
                    hold(emu, key, frames, 60)
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                screenshot(emu, screenshot_path.parent, screenshot_path.name)
                retail_save_from_field(emu, baseline_counter)
                exported = screenshot_path.with_suffix(".sav")
                exported_record = export_backup_artifact(emu, exported)
                exported = artifact_path(exported_record)
                saved_raw = PARTY.extract_raw_save(exported)
                saved_counter, saved_base = PARTY.active_copy(saved_raw)
                location = struct.unpack_from(
                    "<5i",
                    saved_raw,
                    saved_base + LOCAL_FIELD_DATA_OFFSET,
                )
                require(
                    location[:4] == (69, -1, 11, 13),
                    f"retail terminal bootstrap location differs: {location}",
                )
                return {
                    "label": name,
                    "retail_save": True,
                    "location": list(location),
                    "generation": saved_counter,
                    "normal_copies_authenticated": len(
                        PARTY.valid_normal_copies(saved_raw)
                    ),
                    "exported_raw_save": str(exported),
                    "capture": str(screenshot_path),
                }
            elif name == "transfer":
                baseline_counter, _ = PARTY.active_copy(raw)
                baseline_pc_counter, baseline_pc_base = active_pc_copy(raw)
                _, baseline_count, baseline_party = PARTY.party_image(raw)
                require(
                    baseline_count == 5,
                    "transfer input does not have one empty party slot",
                )
                expected_target = pc_box_record(
                    raw, baseline_pc_base, 0, BOX_TARGET_SLOT
                )
                target_pid, target_ot_id, target_species = box_identity(
                    expected_target
                )
                require(
                    target_species == TARGET_SPECIES,
                    "transfer input does not contain the boxed target",
                )
                metadata, initial_history = runtime_history(emu)
                history_index, _, initial_history_moves = find_history_record(
                    initial_history, target_pid, target_ot_id
                )
                require(
                    metadata[4] == 0
                    and initial_history_moves.count(TARGET_MOVE) == 1,
                    "transfer input history is not clean and singular",
                )
                captures: list[str] = []

                # Retail Withdraw: the storage menu starts on Deposit, and its
                # right-hand item is Withdraw. Box1 starts on slot zero and the
                # first context command is the canonical WITHDRAW operation.
                open_retail_pc_storage_menu(emu, terminal_boot=True)
                tap(emu, "RIGHT", 30)
                tap(emu, "A", 180)
                tap(emu, "A", 60)
                touch(emu, 210, 76, 180)
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_withdrawn.png",
                    )
                )
                withdrawn_party = wait_party_locked(emu)
                require(
                    struct.unpack_from("<i", withdrawn_party, 4)[0] == 6,
                    "retail Withdraw did not append party slot 5",
                )
                withdrawn_target = party_record(withdrawn_party, 5)
                require(
                    box_identity(withdrawn_target[:PC_MON_SIZE])[:2]
                    == (target_pid, target_ot_id),
                    "retail Withdraw changed the target PID/OTID",
                )
                withdrawn_metadata, withdrawn_history = runtime_history(emu)
                require(
                    withdrawn_metadata[4] == 0
                    and withdrawn_history == initial_history,
                    "retail Withdraw dirtied or changed move history",
                )

                # Exit Withdraw mode and the PC, then view the moved identity
                # through the actual party Summary and rebuild its candidates.
                tap(emu, "B", 60)
                tap(emu, "DOWN", 20)
                tap(emu, "A", 180)
                touch(emu, 190, 145, 180)
                touch(emu, 100, 146, 180)
                require(
                    box_identity(
                        runtime_box_record(emu, 0, BOX_TARGET_SLOT)
                    )[2]
                    == 0,
                    "retail Withdraw did not commit empty Box1 slot 0 "
                    "when the PC application exited",
                )
                require(
                    runtime_pc_modified_flags(emu) & 1,
                    "retail Withdraw did not mark Box1 dirty at exit",
                )
                open_summary_moves(emu, 5)
                party_state = locate_inactive_summary_state(
                    emu,
                    moves=record_payload(withdrawn_target)[1],
                    owner_pos=5,
                    data_type=1,
                )
                tap(emu, "X", 30)
                withdrawn_candidates = candidate_state(emu, party_state)
                require(
                    withdrawn_candidates["candidates"]
                    == PERSISTED_CANDIDATES,
                    "party Summary candidate order did not follow transfer",
                )
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_party_summary.png",
                    )
                )
                tap(emu, "B", 30)
                tap(emu, "B", 30)
                wait_overlay_active(
                    emu, SUMMARY_RELEARN_OVERLAY_ID, False
                )
                HEADLESS.cycle(emu, 120)
                tap(emu, "B", 120)
                tap(emu, "B", 120)

                # Retail Deposit: reopen the same terminal, choose Deposit,
                # select party slot 5, and use the first DEPOSIT command.
                open_retail_pc_storage_menu(emu, terminal_boot=True)
                touch(emu, 64, 48, 180)
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_deposit_party.png",
                    )
                )
                tap(emu, "DOWN", 30)
                tap(emu, "DOWN", 30)
                tap(emu, "RIGHT", 30)
                tap(emu, "A", 60)
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_deposit_context.png",
                    )
                )
                touch(emu, 210, 76, 180)
                tap(emu, "A", 180)
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_deposited.png",
                    )
                )
                deposited_party = wait_party_locked(emu)
                require(
                    deposited_party == baseline_party,
                    "retail Deposit did not restore the party byte-exact",
                )
                deposited_metadata, deposited_history = runtime_history(emu)
                require(
                    deposited_metadata[4] == 0
                    and deposited_history == initial_history,
                    "retail Deposit dirtied or changed move history",
                )

                tap(emu, "B", 60)
                tap(emu, "DOWN", 20)
                tap(emu, "A", 180)
                touch(emu, 190, 145, 180)
                touch(emu, 100, 146, 180)
                deposited_target = runtime_box_record(
                    emu, 0, BOX_TARGET_SLOT
                )
                require(
                    deposited_target == expected_target,
                    "retail Deposit did not restore Box1 slot 0 "
                    "byte-exact at PC application exit",
                )
                require(
                    runtime_pc_modified_flags(emu) & 1,
                    "retail Withdraw/Deposit did not retain Box1 dirty "
                    "ownership at exit",
                )
                retail_save_from_field(emu, baseline_counter)
                exported = screenshot_path.with_suffix(".sav")
                exported_record = export_backup_artifact(emu, exported)
                exported = artifact_path(exported_record)
                saved_raw = PARTY.extract_raw_save(exported)
                saved_counter, saved_count, saved_party = PARTY.party_image(
                    saved_raw
                )
                saved_pc_counter, saved_pc_base = active_pc_copy(saved_raw)
                require(
                    PARTY.save_counter_compare(
                        saved_counter, baseline_counter
                    )
                    > 0
                    and PARTY.save_counter_compare(
                        saved_pc_counter, baseline_pc_counter
                    )
                    > 0,
                    "retail transfer save did not advance save ownership",
                )
                require(
                    saved_count == 5 and saved_party == baseline_party,
                    "retail transfer save changed the restored party",
                )
                require(
                    saved_raw[
                        saved_pc_base + PC_SAVE_OFFSET:
                        saved_pc_base
                        + PC_SAVE_OFFSET
                        + PC_STORAGE_BOXES_SIZE
                    ]
                    == raw[
                        baseline_pc_base + PC_SAVE_OFFSET:
                        baseline_pc_base
                        + PC_SAVE_OFFSET
                        + PC_STORAGE_BOXES_SIZE
                    ],
                    "retail transfer save changed a boxed record",
                )
                saved_checksums = validate_all_boxed_checksums(
                    saved_raw, saved_pc_base
                )
                validate_all_party_checksums(saved_party)
                _, _, saved_history = selected_persisted_history(saved_raw)
                saved_history_index, _, saved_history_moves = (
                    find_history_record(
                        saved_history, target_pid, target_ot_id
                    )
                )
                require(
                    saved_history == initial_history
                    and saved_history_index == history_index
                    and saved_history_moves.count(TARGET_MOVE) == 1,
                    "retail transfer duplicated or orphaned history",
                )
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_after_save.png",
                    )
                )
                return {
                    "label": name,
                    "actual_retail_withdraw_and_deposit": True,
                    "identity": [target_pid, target_ot_id],
                    "party_slot_after_withdraw": 5,
                    "party_candidate_order": list(
                        withdrawn_candidates["candidates"]
                    ),
                    "box_slot_after_deposit": BOX_TARGET_SLOT,
                    "history_record_index": history_index,
                    "history_move_count": saved_history_moves.count(
                        TARGET_MOVE
                    ),
                    "history_unchanged": True,
                    "box1_dirty_before_save": True,
                    "party_restored_exact": True,
                    "all_900_saved_checksums_valid": len(
                        saved_checksums
                    )
                    == 900,
                    "saved_generation": saved_counter,
                    "saved_pc_generation": saved_pc_counter,
                    "exported_raw_save": str(exported),
                    "captures": captures,
                }
            elif name == "boxed":
                baseline_counter, _ = PARTY.active_copy(raw)
                baseline_pc_counter, baseline_pc_base = active_pc_copy(raw)
                expected_target = pc_box_record(
                    raw, baseline_pc_base, 0, BOX_TARGET_SLOT
                )
                expected_switch = pc_box_record(
                    raw, baseline_pc_base, 0, BOX_SWITCH_SLOT
                )
                target_pid, target_ot_id, _ = box_identity(expected_target)
                metadata, history = runtime_history(emu)
                require(metadata[4] == 0, "boxed scenario history is dirty")
                state, captures = open_retail_box_summary_moves(
                    emu,
                    screenshot_path.parent,
                    screenshot_path.stem,
                    terminal_boot=True,
                )
                inactive_summary_evidence(
                    emu, state, "actual PC Summary moves page"
                )
                assert_box_cancel_exact(
                    emu,
                    expected_target,
                    expected_switch,
                    metadata,
                    history,
                    "actual PC Summary entry",
                )
                transitions: list[dict[str, object]] = []

                # Touch entry, scroll deeply, and cancel byte-exact.
                touch(emu, 40, 140, 60)
                initial = assert_candidate_viewport(
                    emu, state, 0, 0, "boxed touch candidate list"
                )
                require(
                    initial["candidates"] == CONTROLLED_CANDIDATES,
                    "boxed candidate acquisition order differs",
                )
                for _ in range(5):
                    tap(emu, "DOWN", 10)
                scrolled = candidate_state(emu, state)
                require(
                    scrolled["cursor"] == 5 and scrolled["top"] == 2,
                    "boxed list did not scroll to the expected deep viewport",
                )
                tap(emu, "B", 30)
                summary_state_evidence(
                    emu, state, 0, 0, "boxed deep-list cancel"
                )
                assert_box_cancel_exact(
                    emu,
                    expected_target,
                    expected_switch,
                    metadata,
                    history,
                    "boxed deep-list cancel",
                )

                # Re-enter by key and use the actual PC next/previous arrows
                # from list, slot, HM, and confirmation states.
                tap(emu, "X", 30)
                initial = assert_candidate_viewport(
                    emu, state, 0, 0, "boxed key candidate list"
                )
                target_owner = read_u32(
                    emu, state + SUMMARY_STATE_OWNER_POKEMON_OFFSET
                )
                require(
                    target_owner
                    == runtime_box_address(emu, 0, BOX_TARGET_SLOT),
                    "boxed Summary target owner is not canonical PC storage",
                )
                for from_mode in (1, 3, 5, 4):
                    if from_mode == 3:
                        tap(emu, "A", 20)
                    elif from_mode == 5:
                        tap(emu, "A", 20)
                        tap(emu, "A", 30)
                    elif from_mode == 4:
                        tap(emu, "A", 20)
                        for _ in range(3):
                            tap(emu, "DOWN", 8)
                        tap(emu, "A", 30)
                    require(
                        read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET)
                        == from_mode,
                        f"boxed pre-switch mode {from_mode} was not reached",
                    )
                    touch(emu, 215, 115, 30)
                    switched = wait_summary_identity(
                        emu,
                        state,
                        expected_pos=BOX_SWITCH_SLOT,
                        expected_mode=2,
                        expected_owner_pokemon=runtime_box_address(
                            emu, 0, BOX_SWITCH_SLOT
                        ),
                    )
                    transitions.append(
                        {"from_mode": from_mode, "to": "empty", **switched}
                    )
                    assert_box_cancel_exact(
                        emu,
                        expected_target,
                        expected_switch,
                        metadata,
                        history,
                        f"boxed mode {from_mode} next switch",
                    )
                    touch(emu, 215, 50, 30)
                    switched_back = wait_summary_identity(
                        emu,
                        state,
                        expected_pos=BOX_TARGET_SLOT,
                        expected_mode=1,
                        expected_owner_pokemon=target_owner,
                    )
                    require(
                        candidate_state(emu, state)["candidates"]
                        == initial["candidates"],
                        f"boxed mode {from_mode} switch retained peer state",
                    )
                    transitions.append(
                        {"from_mode": 2, "to": "list", **switched_back}
                    )

                # Permanent mutation occurs only after this explicit confirm.
                tap(emu, "A", 20)
                for _ in range(3):
                    tap(emu, "DOWN", 8)
                tap(emu, "A", 30)
                tap(emu, "A", 120)
                summary_state_evidence(
                    emu, state, 6, 1, "boxed confirmed replacement"
                )
                changed_target = runtime_box_record(
                    emu, 0, BOX_TARGET_SLOT
                )
                _, changed_moves, changed_pp, changed_pp_ups = (
                    box_record_payload(changed_target)
                )
                require(
                    changed_moves == (57, 48, 352, TARGET_MOVE)
                    and changed_pp[TARGET_REPLACEMENT_SLOT] == 8
                    and changed_pp_ups[TARGET_REPLACEMENT_SLOT] == 0,
                    "boxed replacement move/PP/PP Ups differ",
                )
                validate_box_checksum(changed_target, "runtime boxed target")
                require(
                    runtime_box_record(emu, 0, BOX_SWITCH_SLOT)
                    == expected_switch,
                    "boxed replacement changed the switch peer",
                )
                require(
                    runtime_pc_modified_flags(emu) == 0,
                    "Summary dirtied PC storage before returning to its parent",
                )
                committed_metadata, committed_history = runtime_history(emu)
                history_index, _, history_moves_before = find_history_record(
                    history, target_pid, target_ot_id
                )
                committed_index, _, history_moves_after = find_history_record(
                    committed_history, target_pid, target_ot_id
                )
                require(
                    committed_index == history_index
                    and history_moves_after[
                        :len(history_moves_before)
                    ]
                    == history_moves_before
                    and history_moves_after.count(TARGET_MOVE) == 1,
                    "boxed replacement did not update one identity record once",
                )
                for index, (old, new) in enumerate(
                    zip(
                        history_records(history),
                        history_records(committed_history),
                    )
                ):
                    if index != history_index:
                        require(
                            old == new,
                            f"boxed replacement changed history record {index}",
                        )
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_boxed_success.png",
                    )
                )

                # A real switch from success keeps the confirmed write, drops
                # only old modal state, and rebuilds the target without the
                # newly known move when switching back.
                touch(emu, 215, 115, 30)
                wait_summary_identity(
                    emu,
                    state,
                    expected_pos=BOX_SWITCH_SLOT,
                    expected_mode=2,
                )
                touch(emu, 215, 50, 30)
                wait_summary_identity(
                    emu,
                    state,
                    expected_pos=BOX_TARGET_SLOT,
                    expected_mode=1,
                )
                require(
                    TARGET_MOVE
                    not in candidate_state(emu, state)["candidates"],
                    "boxed success switch rebuilt a now-known candidate",
                )
                tap(emu, "B", 30)
                tap(emu, "B", 180)
                require(
                    runtime_pc_modified_flags(emu) & 1,
                    "PC Summary parent did not dirty the active box",
                )
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_pc_parent_dirty.png",
                    )
                )
                exit_pc_and_retail_save(emu, baseline_counter)
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_after_save.png",
                    )
                )
                exported = screenshot_path.with_suffix(".sav")
                exported_record = export_backup_artifact(emu, exported)
                exported = artifact_path(exported_record)
                saved_raw = PARTY.extract_raw_save(exported)
                saved_counter, saved_count, saved_party = PARTY.party_image(
                    saved_raw
                )
                saved_pc_counter, saved_pc_base = active_pc_copy(saved_raw)
                saved_target = pc_box_record(
                    saved_raw, saved_pc_base, 0, BOX_TARGET_SLOT
                )
                saved_switch = pc_box_record(
                    saved_raw, saved_pc_base, 0, BOX_SWITCH_SLOT
                )
                require(
                    PARTY.save_counter_compare(
                        saved_counter, baseline_counter
                    )
                    > 0
                    and PARTY.save_counter_compare(
                        saved_pc_counter, baseline_pc_counter
                    )
                    > 0,
                    "boxed retail save did not publish newer generations",
                )
                require(
                    saved_count == 5
                    and saved_party == expected_party,
                    "boxed path changed one or more party records",
                )
                validate_all_party_checksums(saved_party)
                require(
                    PARTY.summarize_party(saved_party)[4]["shiny"] is True,
                    "boxed path corrupted shiny Pidgey",
                )
                require(
                    saved_target == changed_target
                    and saved_switch == expected_switch,
                    "boxed replacement did not persist exactly",
                )
                for box in range(PC_BOX_COUNT):
                    for slot in range(PC_MONS_PER_BOX):
                        if box == 0 and slot == BOX_TARGET_SLOT:
                            continue
                        require(
                            pc_box_record(
                                saved_raw, saved_pc_base, box, slot
                            )
                            == pc_box_record(
                                raw, baseline_pc_base, box, slot
                            ),
                            f"unrelated PC box {box} slot {slot} changed",
                        )
                saved_checksums = validate_all_boxed_checksums(
                    saved_raw, saved_pc_base
                )
                _, _, persisted_history = selected_persisted_history(
                    saved_raw
                )
                persisted_index, _, persisted_moves = find_history_record(
                    persisted_history, target_pid, target_ot_id
                )
                require(
                    persisted_index == history_index
                    and persisted_moves.count(TARGET_MOVE) == 1,
                    "boxed history did not persist once",
                )
                return {
                    "label": name,
                    "actual_terminal_and_pc_ui": True,
                    "actual_box_summary": True,
                    "switch_transitions": transitions,
                    "candidate_order": list(initial["candidates"]),
                    "confirmed_moves": list(changed_moves),
                    "confirmed_pp": list(changed_pp),
                    "confirmed_pp_ups": list(changed_pp_ups),
                    "pc_parent_dirty_flags": 1,
                    "saved_pc_generation": saved_pc_counter,
                    "all_900_saved_checksums_valid": len(
                        saved_checksums
                    )
                    == 900,
                    "party_exact": True,
                    "shiny_pidgey_valid": True,
                    "history_record_index": history_index,
                    "history_move_count": history_moves_after.count(
                        TARGET_MOVE
                    ),
                    "exported_raw_save": str(exported),
                    "captures": captures,
                }
            elif name == "boxed_reload":
                _, persisted_pc_base = active_pc_copy(raw)
                persisted_target = pc_box_record(
                    raw, persisted_pc_base, 0, BOX_TARGET_SLOT
                )
                _, persisted_moves, persisted_pp, persisted_pp_ups = (
                    box_record_payload(persisted_target)
                )
                require(
                    persisted_moves == (57, 48, 352, TARGET_MOVE)
                    and persisted_pp[TARGET_REPLACEMENT_SLOT] == 8
                    and persisted_pp_ups[TARGET_REPLACEMENT_SLOT] == 0,
                    "boxed reload input lacks the persisted replacement",
                )
                state, captures = open_retail_box_summary_moves(
                    emu,
                    screenshot_path.parent,
                    screenshot_path.stem,
                    terminal_boot=True,
                )
                tap(emu, "X", 30)
                reloaded = candidate_state(emu, state)
                require(
                    TARGET_MOVE not in reloaded["candidates"],
                    "fresh PC Summary still offers the persisted move",
                )
                touch(emu, 215, 115, 30)
                wait_summary_identity(
                    emu,
                    state,
                    expected_pos=BOX_SWITCH_SLOT,
                    expected_mode=2,
                )
                touch(emu, 215, 50, 30)
                wait_summary_identity(
                    emu,
                    state,
                    expected_pos=BOX_TARGET_SLOT,
                    expected_mode=1,
                )
                tap(emu, "B", 30)
                metadata, persisted_history = runtime_history(emu)
                pid, ot_id, _ = box_identity(persisted_target)
                history_index, _, history_moves = find_history_record(
                    persisted_history, pid, ot_id
                )
                require(
                    history_moves.count(TARGET_MOVE) == 1,
                    "fresh reload history duplicated the boxed move",
                )
                _, _, reloaded_party = PARTY.party_image(raw)
                validate_all_party_checksums(reloaded_party)
                reloaded_checksums = validate_all_boxed_checksums(
                    raw, persisted_pc_base
                )
                require(
                    PARTY.summarize_party(reloaded_party)[4]["shiny"] is True,
                    "fresh boxed reload corrupted shiny Pidgey",
                )
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_persisted_summary.png",
                    )
                )
                return {
                    "label": name,
                    "actual_terminal_and_pc_ui": True,
                    "actual_box_summary": True,
                    "persisted_moves": list(persisted_moves),
                    "persisted_pp": list(persisted_pp),
                    "persisted_pp_ups": list(persisted_pp_ups),
                    "candidate_order_without_known_move": list(
                        reloaded["candidates"]
                    ),
                    "history_record_index": history_index,
                    "history_move_count": history_moves.count(TARGET_MOVE),
                    "history_dirty": metadata[4],
                    "all_900_checksums_valid": len(reloaded_checksums)
                    == 900,
                    "captures": captures,
                }
            elif name == "transfer_reload":
                _, persisted_pc_base = active_pc_copy(raw)
                persisted_target = pc_box_record(
                    raw, persisted_pc_base, 0, BOX_TARGET_SLOT
                )
                pid, ot_id, species = box_identity(persisted_target)
                require(
                    species == TARGET_SPECIES,
                    "transfer reload lost the boxed target",
                )
                _, count, persisted_party = PARTY.party_image(raw)
                require(
                    count == 5,
                    "transfer reload did not retain the restored party count",
                )
                validate_all_party_checksums(persisted_party)
                persisted_checksums = validate_all_boxed_checksums(
                    raw, persisted_pc_base
                )
                _, _, persisted_history = selected_persisted_history(raw)
                history_index, _, history_moves = find_history_record(
                    persisted_history, pid, ot_id
                )
                require(
                    history_moves.count(TARGET_MOVE) == 1,
                    "transfer reload duplicated or orphaned history",
                )
                state, captures = open_retail_box_summary_moves(
                    emu,
                    screenshot_path.parent,
                    screenshot_path.stem,
                    terminal_boot=True,
                )
                tap(emu, "X", 30)
                reloaded = candidate_state(emu, state)
                require(
                    reloaded["candidates"] == PERSISTED_CANDIDATES,
                    "boxed candidate order changed after transfer reload",
                )
                metadata, runtime_persisted_history = runtime_history(emu)
                require(
                    metadata[4] == 0
                    and runtime_persisted_history == persisted_history,
                    "transfer reload selected dirty or different history",
                )
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_continuity.png",
                    )
                )
                return {
                    "label": name,
                    "actual_terminal_and_pc_ui": True,
                    "actual_box_summary": True,
                    "identity": [pid, ot_id],
                    "box_slot": BOX_TARGET_SLOT,
                    "candidate_order": list(reloaded["candidates"]),
                    "history_record_index": history_index,
                    "history_move_count": history_moves.count(TARGET_MOVE),
                    "history_dirty": metadata[4],
                    "all_900_checksums_valid": len(
                        persisted_checksums
                    )
                    == 900,
                    "party_count": count,
                    "captures": captures,
                }
            elif name == "pc_teardown":
                require(
                    not overlay_is_active(emu, SUMMARY_RELEARN_OVERLAY_ID),
                    "PC lifecycle booted with overlay 154 active",
                )
                registry_before = overlay_registry(emu)
                baseline_party = runtime_party(emu)
                baseline_pc = read_bytes(
                    emu, runtime_pc_storage_address(emu), PC_SAVE_SIZE
                )
                baseline_metadata, baseline_history = runtime_history(emu)
                target_moves = box_record_payload(
                    runtime_box_record(emu, 0, BOX_TARGET_SLOT)
                )[1]
                captures: list[str] = []
                open_retail_pc_move_ui(emu, terminal_boot=True)
                touch(emu, 16, 56, 60)
                touch(emu, 210, 76, 180)
                first_load_frames = wait_overlay_active(
                    emu, SUMMARY_RELEARN_OVERLAY_ID, True
                )
                registry_first_child = overlay_registry(emu)
                first_state = locate_inactive_summary_state(
                    emu,
                    moves=target_moves,
                    owner_pos=BOX_TARGET_SLOT,
                    data_type=2,
                    page_mode=None,
                )
                require(
                    read_bytes(
                        emu, first_state, SUMMARY_STATE_EXTENSION_SIZE
                    )
                    == bytes(SUMMARY_STATE_EXTENSION_SIZE),
                    "first nested PC Summary extension was not fresh-zero",
                )
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_first_child.png",
                    )
                )
                tap(emu, "RIGHT", 80)
                tap(emu, "X", 20)
                active_state = locate_summary_relearn_state(
                    emu,
                    original_moves=target_moves,
                    owner_pos=BOX_TARGET_SLOT,
                )
                summary_state_evidence(
                    emu, active_state, 1, 0, "first nested PC child"
                )
                tap(emu, "B", 20)
                summary_state_evidence(
                    emu, active_state, 0, 0, "first PC modal cancel"
                )
                tap(emu, "B", 40)
                first_unload_frames = wait_overlay_active(
                    emu, SUMMARY_RELEARN_OVERLAY_ID, False
                )
                HEADLESS.cycle(emu, 120)
                registry_first_parent = overlay_registry(emu)
                require(
                    runtime_party(emu) == baseline_party
                    and read_bytes(
                        emu,
                        runtime_pc_storage_address(emu),
                        PC_SAVE_SIZE,
                    )
                    == baseline_pc
                    and runtime_history(emu)
                    == (baseline_metadata, baseline_history),
                    "first nested PC return changed owners",
                )
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_first_parent.png",
                    )
                )

                # The retail context menu is still open on the same boxed
                # identity. Reopen its real Summary child without replacing
                # the parent or synthesizing an overlay pointer.
                touch(emu, 210, 76, 180)
                second_load_frames = wait_overlay_active(
                    emu, SUMMARY_RELEARN_OVERLAY_ID, True
                )
                registry_second_child = overlay_registry(emu)
                second_state = locate_inactive_summary_state(
                    emu,
                    moves=target_moves,
                    owner_pos=BOX_TARGET_SLOT,
                    data_type=2,
                    page_mode=None,
                )
                require(
                    read_bytes(
                        emu, second_state, SUMMARY_STATE_EXTENSION_SIZE
                    )
                    == bytes(SUMMARY_STATE_EXTENSION_SIZE),
                    "second nested PC Summary retained extension bytes",
                )
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_second_child.png",
                    )
                )
                tap(emu, "RIGHT", 80)
                tap(emu, "X", 20)
                second_active = locate_summary_relearn_state(
                    emu,
                    original_moves=target_moves,
                    owner_pos=BOX_TARGET_SLOT,
                )
                tap(emu, "B", 20)
                summary_state_evidence(
                    emu, second_active, 0, 0, "second PC modal cancel"
                )
                tap(emu, "B", 40)
                second_unload_frames = wait_overlay_active(
                    emu, SUMMARY_RELEARN_OVERLAY_ID, False
                )
                HEADLESS.cycle(emu, 120)
                registry_second_parent = overlay_registry(emu)
                require(
                    runtime_party(emu) == baseline_party
                    and read_bytes(
                        emu,
                        runtime_pc_storage_address(emu),
                        PC_SAVE_SIZE,
                    )
                    == baseline_pc
                    and runtime_history(emu)
                    == (baseline_metadata, baseline_history),
                    "second nested PC return changed owners",
                )
                captures.append(
                    screenshot(
                        emu,
                        screenshot_path.parent,
                        f"{screenshot_path.stem}_second_parent.png",
                    )
                )
                return {
                    "label": name,
                    "actual_terminal_pc_parent": True,
                    "actual_nested_summary_children": 2,
                    "overlay154_inactive_before": True,
                    "overlay154_active_first_child": True,
                    "overlay154_inactive_first_parent": True,
                    "overlay154_active_second_child": True,
                    "overlay154_inactive_second_parent": True,
                    "first_extension_zero_bytes": SUMMARY_STATE_EXTENSION_SIZE,
                    "second_extension_zero_bytes": SUMMARY_STATE_EXTENSION_SIZE,
                    "first_load_frames": first_load_frames,
                    "first_unload_frames": first_unload_frames,
                    "second_load_frames": second_load_frames,
                    "second_unload_frames": second_unload_frames,
                    "registries": {
                        "before": registry_before,
                        "first_child": registry_first_child,
                        "first_parent": registry_first_parent,
                        "second_child": registry_second_child,
                        "second_parent": registry_second_parent,
                    },
                    "party_pc_history_exact": True,
                    "captures": captures,
                }
            else:
                require(
                    not overlay_is_active(emu, SUMMARY_RELEARN_OVERLAY_ID),
                    f"{name} overlay 154 active before Summary",
                )
                open_summary_moves(emu, TARGET_SLOT)
                wait_overlay_active(
                    emu, SUMMARY_RELEARN_OVERLAY_ID, True
                )
                party, _ = PARTY.wait_for_runtime_party(
                    emu, expected_party, maximum_frames=90
                )
                metadata, history = runtime_history(emu)
                touch(emu, 40, 140, 40)
                state = locate_summary_relearn_state(emu)
                owner = read_u32(emu, state)
                if name == "identity":
                    sentinel_move = 777
                    write_u16(
                        emu, owner + SUMMARY_BASE_MOVE_OFFSET, sentinel_move
                    )
                    write_u32(emu, state, owner + 4)
                    HEADLESS.cycle(emu, 10)
                    require(
                        read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET) == 0,
                        "pointer identity boundary retained modal state",
                    )
                    require(
                        read_u16(emu, owner + SUMMARY_BASE_MOVE_OFFSET)
                        == sentinel_move,
                        "pointer identity overwrote new-owner move",
                    )
                    detail = {
                        "mode": 0,
                        "new_owner_move_preserved": sentinel_move,
                    }
                elif name == "position":
                    original = read_u16(
                        emu,
                        state + SUMMARY_STATE_ORIGINAL_ARG_MOVE_OFFSET,
                    )
                    write_u8(emu, owner + 0x14, 1)
                    HEADLESS.cycle(emu, 10)
                    require(
                        read_u8(emu, state + SUMMARY_STATE_MODE_OFFSET) == 0,
                        "position boundary retained modal state",
                    )
                    require(
                        read_u16(emu, owner + SUMMARY_BASE_MOVE_OFFSET)
                        == original,
                        "same-owner boundary did not restore args->move",
                    )
                    detail = {
                        "mode": 0,
                        "original_arg_move_restored": original,
                    }
                elif name == "teardown":
                    summary_state_evidence(
                        emu, state, 1, 0, "active before teardown"
                    )
                    tap(emu, "B", 20)
                    summary_state_evidence(
                        emu, state, 0, 0, "modal cancel before Summary exit"
                    )
                    assert_cancel_exact(
                        emu,
                        party,
                        metadata,
                        history,
                        "modal cancel before Summary exit",
                    )
                    tap(emu, "B", 20)
                    first_unload_frames = wait_overlay_active(
                        emu, SUMMARY_RELEARN_OVERLAY_ID, False
                    )
                    HEADLESS.cycle(emu, 150)
                    assert_cancel_exact(
                        emu,
                        party,
                        metadata,
                        history,
                        "real Summary exit",
                    )
                    party_exit_path = screenshot_path.with_name(
                        screenshot_path.stem
                        + "_party_exit"
                        + screenshot_path.suffix
                    )
                    screenshot(
                        emu, party_exit_path.parent, party_exit_path.name
                    )

                    # The returned Party menu retains the selected Pokémon.
                    tap(emu, "A", 30)
                    tap(emu, "A", 100)
                    tap(emu, "RIGHT", 80)
                    wait_overlay_active(
                        emu, SUMMARY_RELEARN_OVERLAY_ID, True
                    )
                    fresh_state = locate_inactive_summary_state(emu)
                    inactive_summary_evidence(
                        emu, fresh_state, "fresh Summary after overlay reload"
                    )
                    require(
                        read_u16(
                            emu,
                            fresh_state
                            + SUMMARY_STATE_CANDIDATE_COUNT_OFFSET,
                        )
                        == 0
                        and read_u16(
                            emu,
                            fresh_state
                            + SUMMARY_STATE_PENDING_MOVE_OFFSET,
                        )
                        == 0,
                        "fresh Summary retained prior modal data",
                    )
                    assert_cancel_exact(
                        emu,
                        party,
                        metadata,
                        history,
                        "fresh Summary after overlay reload",
                    )
                    tap(emu, "X", 20)
                    fresh_state = locate_summary_relearn_state(emu)
                    fresh_view = assert_candidate_viewport(
                        emu,
                        fresh_state,
                        0,
                        0,
                        "reloaded Summary candidate list",
                    )
                    tap(emu, "B", 20)
                    summary_state_evidence(
                        emu,
                        fresh_state,
                        0,
                        0,
                        "reloaded Summary modal cancel",
                    )
                    assert_cancel_exact(
                        emu,
                        party,
                        metadata,
                        history,
                        "reloaded Summary modal cancel",
                    )
                    tap(emu, "B", 20)
                    second_unload_frames = wait_overlay_active(
                        emu, SUMMARY_RELEARN_OVERLAY_ID, False
                    )
                    HEADLESS.cycle(emu, 120)
                    assert_cancel_exact(
                        emu,
                        party,
                        metadata,
                        history,
                        "second real Summary exit",
                    )
                    detail = {
                        "mode_before_exit": 1,
                        "overlay_active_before_exit": True,
                        "first_unload_frames": first_unload_frames,
                        "party_exit_screenshot": str(party_exit_path),
                        "overlay_reloaded": True,
                        "fresh_mode": 0,
                        "fresh_candidate_count": 0,
                        "fresh_pending_move": 0,
                        "reentry_candidate_count": fresh_view["count"],
                        "second_unload_frames": second_unload_frames,
                        "overlay_inactive_after_second_exit": True,
                    }
                else:
                    raise RuntimeError(f"unknown isolated scenario: {name}")
            assert_cancel_exact(
                emu, party, metadata, history, f"{name} scenario"
            )
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)
            screenshot(emu, screenshot_path.parent, screenshot_path.name)
            return {
                "label": name,
                **detail,
                "party_sha256": hashlib.sha256(party).hexdigest(),
                "history_sha256": hashlib.sha256(history).hexdigest(),
                "dirty": metadata[4],
            }
        finally:
            close_emulator(emu, imported)


def isolated_scenario_evidence(
    rom: Path,
    raw_path: Path,
    name: str,
    screenshot_path: Path,
) -> dict[str, object]:
    raw_before = raw_path.read_bytes()
    raw_sha256 = hashlib.sha256(raw_before).hexdigest()
    completed = subprocess.run(
        [
            BOOTSTRAP_PYTHON_PATH,
            "-I",
            "-S",
            "-B",
            "-X",
            "pycache_prefix=/dev/null",
            str(Path(BOOTSTRAP_LAUNCHER_PATH).resolve()),
            "--rom",
            str(rom),
            "--probe-raw",
            str(raw_path),
            "--expected-probe-raw-sha256",
            raw_sha256,
            "--scenario",
            name,
            "--probe-screenshot",
            str(screenshot_path),
            *SUBPROCESS_AUTHENTICATION_ARGS,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=dict(BOOTSTRAP_CHILD_ENVIRONMENT),
        timeout=240,
    )
    require(
        completed.returncode == 0,
        f"{name} subprocess failed: " + completed.stderr[-1000:],
    )
    evidence = json.loads(completed.stdout)
    require(
        completed.stdout
        == json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        f"{name} subprocess output is not canonical",
    )
    verify_authenticated_result(evidence)
    require(
        evidence.get("label") == name,
        f"{name} subprocess returned the wrong scenario label",
    )
    require(
        evidence.get("artifact_authentication")
        == BOOTSTRAP_AUTHENTICATION,
        f"{name} subprocess artifact authentication differs",
    )
    require(
        evidence.get("probe_raw_sha256") == raw_sha256
        and hashlib.sha256(raw_path.read_bytes()).hexdigest() == raw_sha256,
        f"{name} controlled raw changed across parent/child execution",
    )
    return evidence


def task6_serialization_surrogate_evidence(
    controlled_raw: bytes,
    controlled_history_payload: bytes,
    box_fixture: dict[str, object],
) -> dict[str, object]:
    """Exercise authenticated save/identity boundaries without a radio peer."""

    pc_copies = valid_pc_copies(controlled_raw)
    require(
        len(pc_copies) == len(PARTY.SAVE_COPY_BASES),
        "task-6 surrogate requires both authenticated PC generations",
    )
    _, active_base = active_pc_copy(controlled_raw)
    source = pc_box_record(
        controlled_raw, active_base, 0, BOX_TARGET_SLOT
    )
    switch = pc_box_record(
        controlled_raw, active_base, 0, BOX_SWITCH_SLOT
    )
    source_identity = box_identity(source)[:2]
    source_history = find_history_record(
        controlled_history_payload
        + bytes(HISTORY_IMAGE_SIZE - len(controlled_history_payload)),
        *source_identity,
    )[2]
    require(
        source == box_fixture["target"]
        and source_history == CONTROLLED_HISTORY_MOVES,
        "task-6 surrogate source identity/history differs",
    )
    empty_slots = [
        slot
        for slot in range(2, PC_MONS_PER_BOX)
        if box_identity(
            pc_box_record(controlled_raw, active_base, 0, slot)
        )[2]
        == 0
    ]
    require(
        len(empty_slots) >= 2,
        "task-6 surrogate needs two canonical empty PC slots",
    )
    walker_slot, arrival_slot = empty_slots[:2]
    canonical_empty = pc_box_record(
        controlled_raw, active_base, 0, walker_slot
    )

    def replace_pc_slots(
        original: bytes,
        replacements: dict[tuple[int, int], bytes],
    ) -> bytes:
        updated = bytearray(original)
        copies = valid_pc_copies(original)
        require(
            len(copies) == len(PARTY.SAVE_COPY_BASES),
            "PC transaction source is not fully authenticated",
        )
        for _, base in copies:
            for (box, slot), record in replacements.items():
                validate_box_checksum(record, "PC transaction record")
                start = (
                    base
                    + PC_SAVE_OFFSET
                    + box * PC_BOX_SIZE
                    + slot * PC_MON_SIZE
                )
                updated[start:start + PC_MON_SIZE] = record
            footer = base + PC_SAVE_OFFSET + PC_SAVE_SIZE - PC_FOOTER_SIZE
            struct.pack_into(
                "<H",
                updated,
                footer + 0x0E,
                PARTY.crc16_ccitt_false(
                    bytes(updated[base + PC_SAVE_OFFSET:footer])
                ),
            )
        result = bytes(updated)
        require(
            len(valid_pc_copies(result)) == len(PARTY.SAVE_COPY_BASES),
            "PC transaction did not reauthenticate both generations",
        )
        return result

    def assert_pc_transaction_diff(
        before: bytes,
        after: bytes,
        slots: tuple[tuple[int, int], ...],
    ) -> None:
        allowed: set[int] = set()
        for _, base in pc_copies:
            for box, slot in slots:
                start = (
                    base
                    + PC_SAVE_OFFSET
                    + box * PC_BOX_SIZE
                    + slot * PC_MON_SIZE
                )
                allowed.update(range(start, start + PC_MON_SIZE))
            footer = base + PC_SAVE_OFFSET + PC_SAVE_SIZE - PC_FOOTER_SIZE
            allowed.update((footer + 0x0E, footer + 0x0F))
        changed = {
            index
            for index, (old, new) in enumerate(zip(before, after))
            if old != new
        }
        require(
            changed and changed <= allowed,
            "PC transaction changed bytes outside its records/CRC",
        )

    def seal_history(original: bytes, payload: bytes) -> bytes:
        updated = bytearray(original)
        for mirror, offset in enumerate(HISTORY_MIRROR_OFFSETS):
            old_image = original[offset:offset + HISTORY_IMAGE_SIZE]
            require(
                valid_history_image(old_image, mirror),
                f"history mirror {mirror} is not authenticated",
            )
            counter = struct.unpack_from(
                "<I", old_image, HISTORY_FOOTER_OFFSET + 4
            )[0]
            updated[offset:offset + HISTORY_IMAGE_SIZE] = (
                history_image_for_mirror(payload, mirror, counter)
            )
        return bytes(updated)

    def assert_serialized_path(
        saved: bytes,
        slot: int,
        expected_box: bytes,
        identity: tuple[int, int],
        current_moves: tuple[int, ...],
        history_moves: tuple[int, ...],
    ) -> str:
        reparsed_path = bytes(bytearray(saved))
        _, path_base = active_pc_copy(reparsed_path)
        path_record = pc_box_record(reparsed_path, path_base, 0, slot)
        _, _, path_history = selected_persisted_history(reparsed_path)
        require(
            path_record == expected_box
            and box_identity(path_record)[:2] == identity
            and tuple(
                move
                for move in box_record_payload(path_record)[1]
                if move != 0
            )
            == current_moves
            and history_identity_count(path_history, *identity) == 1
            and find_history_record(path_history, *identity)[2]
            == history_moves
            and len(validate_all_boxed_checksums(
                reparsed_path, path_base
            ))
            == 900
            and all(
                valid_history_image(
                    reparsed_path[
                        offset:offset + HISTORY_IMAGE_SIZE
                    ],
                    mirror,
                )
                for mirror, offset in enumerate(HISTORY_MIRROR_OFFSETS)
            ),
            "serialized task-6 path failed authenticated save/reparse",
        )
        before_records = history_records(
            controlled_history_payload
            + bytes(HISTORY_IMAGE_SIZE - len(controlled_history_payload))
        )
        for index, record in enumerate(history_records(path_history)):
            if struct.unpack_from("<II", record) != identity:
                require(
                    record == before_records[index],
                    f"serialized task-6 path changed unrelated record {index}",
                )
        return hashlib.sha256(reparsed_path).hexdigest()

    # Trade staging/cancel leaves canonical save bytes exact. Commit replaces
    # the slot first, then seeds only the incoming identity's current moves.
    incoming_moves = (90, 91, 92, 93)
    incoming = controlled_box_record(
        switch,
        ot_id_xor=0x5A5AA5A5,
        moves=incoming_moves,
        pp=(10, 10, 10, 10),
        pp_ups=(0, 0, 0, 0),
    )
    incoming_identity = box_identity(incoming)[:2]
    staged_trade = bytes(incoming)
    occupied_destination = pc_box_record(
        controlled_raw, active_base, 0, BOX_TARGET_SLOT
    )
    destination_accepts_trade = box_identity(occupied_destination)[2] == 0
    failed_trade = controlled_raw
    if destination_accepts_trade:
        failed_trade = replace_pc_slots(
            controlled_raw, {(0, BOX_TARGET_SLOT): staged_trade}
        )
    require(
        not destination_accepts_trade
        and validate_box_checksum(
            staged_trade, "staged failed-trade transit owner"
        )["valid"]
        and failed_trade == controlled_raw,
        "occupied-destination trade abort changed canonical save bytes",
    )
    trade_pc = replace_pc_slots(
        controlled_raw, {(0, BOX_TARGET_SLOT): incoming}
    )
    assert_pc_transaction_diff(
        controlled_raw, trade_pc, ((0, BOX_TARGET_SLOT),)
    )
    trade_payload = bytearray(controlled_history_payload)
    seed_history_record(trade_payload, incoming, incoming_moves)
    trade_raw = seal_history(trade_pc, bytes(trade_payload))
    _, trade_base = active_pc_copy(trade_raw)
    trade_image = (
        bytes(trade_payload)
        + bytes(HISTORY_IMAGE_SIZE - len(trade_payload))
    )
    require(
        source_identity != incoming_identity
        and pc_box_record(trade_raw, trade_base, 0, BOX_TARGET_SLOT)
        == incoming
        and history_identity_count(trade_image, *source_identity) == 1
        and history_identity_count(trade_image, *incoming_identity) == 1
        and find_history_record(
            trade_image, *source_identity
        )[2]
        == source_history
        and find_history_record(
            trade_image, *incoming_identity
        )[2]
        == incoming_moves,
        "trade commit contaminated outgoing/incoming history",
    )
    trade_reparse_sha256 = assert_serialized_path(
        trade_raw,
        BOX_TARGET_SLOT,
        incoming,
        incoming_identity,
        incoming_moves,
        incoming_moves,
    )

    # Rotom appliance rewrite retains PID/OTID and appends only the proven move.
    form_before_moves = (84, 86, 87, 88)
    form_before = authenticated_box_variant(
        controlled_box_record(
            source,
            ot_id_xor=0x3333CCCC,
            moves=form_before_moves,
            pp=(10, 10, 10, 10),
            pp_ups=(0, 0, 0, 0),
        ),
        species=479,
        form=0,
        is_egg=False,
    )
    form_after_moves = (84, 315, 87, 88)
    form_after = authenticated_box_variant(
        controlled_box_record(
            form_before,
            ot_id_xor=0,
            moves=form_after_moves,
            pp=(10, 10, 10, 10),
            pp_ups=(0, 0, 0, 0),
        ),
        species=479,
        form=1,
        is_egg=False,
    )
    form_identity = box_identity(form_before)[:2]
    form_payload = bytearray(controlled_history_payload)
    seed_history_record(form_payload, form_before, form_before_moves)
    seed_history_record(
        form_payload, form_after, form_before_moves + (315,)
    )
    form_image = (
        bytes(form_payload)
        + bytes(HISTORY_IMAGE_SIZE - len(form_payload))
    )
    require(
        box_identity(form_after)[:2] == form_identity
        and box_identity(form_after)[2] == 479
        and serialized_form_and_egg(form_after) == (1, False)
        and box_record_payload(form_after)[1] == form_after_moves
        and history_identity_count(form_image, *form_identity) == 1
        and find_history_record(
            form_image, *form_identity
        )[2]
        == form_before_moves + (315,),
        "persistent form rewrite lost identity/acquisition ordering",
    )
    invalid_form_record = form_after
    invalid_form_history = bytes(form_payload)
    invalid_form_rejected = False
    try:
        authenticated_box_variant(form_after, form=32)
    except RuntimeError:
        invalid_form_rejected = True
    require(
        invalid_form_rejected
        and form_after == invalid_form_record
        and bytes(form_payload) == invalid_form_history,
        "invalid form did not fail closed before mutation",
    )
    form_pc = replace_pc_slots(
        controlled_raw, {(0, walker_slot): form_after}
    )
    assert_pc_transaction_diff(
        controlled_raw, form_pc, ((0, walker_slot),)
    )
    form_raw = seal_history(form_pc, bytes(form_payload))
    form_reparse_sha256 = assert_serialized_path(
        form_raw,
        walker_slot,
        form_after,
        form_identity,
        form_after_moves,
        form_before_moves + (315,),
    )

    # Egg construction is history-free; hatch seeds inherited current moves
    # for the egg identity without copying parent or prior-slot history.
    egg_moves = (45, 98)
    egg = authenticated_box_variant(
        controlled_box_record(
            switch,
            ot_id_xor=0xA55AA55A,
            moves=(45, 98, 0, 0),
            pp=(10, 10, 0, 0),
            pp_ups=(0, 0, 0, 0),
        ),
        is_egg=True,
    )
    egg_identity = box_identity(egg)[:2]
    controlled_image = (
        controlled_history_payload
        + bytes(HISTORY_IMAGE_SIZE - len(controlled_history_payload))
    )
    parent_record = find_history_record(
        controlled_image, *source_identity
    )[1]
    require(
        serialized_form_and_egg(egg)[1]
        and history_identity_count(controlled_image, *egg_identity) == 0,
        "egg construction allocated learned-move history",
    )
    hatched = authenticated_box_variant(egg, is_egg=False)
    hatch_payload = bytearray(controlled_history_payload)
    seed_history_record(hatch_payload, hatched, egg_moves)
    hatch_image = (
        bytes(hatch_payload)
        + bytes(HISTORY_IMAGE_SIZE - len(hatch_payload))
    )
    require(
        not serialized_form_and_egg(hatched)[1]
        and box_identity(hatched)[:2] == egg_identity
        and history_identity_count(hatch_image, *egg_identity) == 1
        and find_history_record(
            hatch_image, *egg_identity
        )[2]
        == egg_moves
        and find_history_record(
            hatch_image, *source_identity
        )[1]
        == parent_record,
        "hatch baseline inherited parent or prior-slot history",
    )
    egg_pc = replace_pc_slots(
        controlled_raw, {(0, arrival_slot): egg}
    )
    assert_pc_transaction_diff(
        controlled_raw, egg_pc, ((0, arrival_slot),)
    )
    _, egg_base = active_pc_copy(egg_pc)
    _, _, egg_persisted_history = selected_persisted_history(egg_pc)
    require(
        pc_box_record(egg_pc, egg_base, 0, arrival_slot) == egg
        and serialized_form_and_egg(
            pc_box_record(egg_pc, egg_base, 0, arrival_slot)
        )[1]
        and history_identity_count(
            egg_persisted_history, *egg_identity
        )
        == 0
        and all(
            valid_history_image(
                egg_pc[offset:offset + HISTORY_IMAGE_SIZE], mirror
            )
            for mirror, offset in enumerate(HISTORY_MIRROR_OFFSETS)
        ),
        "serialized egg construction allocated history before hatch",
    )
    hatch_pc = replace_pc_slots(
        egg_pc, {(0, arrival_slot): hatched}
    )
    assert_pc_transaction_diff(
        egg_pc, hatch_pc, ((0, arrival_slot),)
    )
    hatch_raw = seal_history(hatch_pc, bytes(hatch_payload))
    hatch_reparse_sha256 = assert_serialized_path(
        hatch_raw,
        arrival_slot,
        hatched,
        egg_identity,
        egg_moves,
        egg_moves,
    )

    # No headless radio peer exists. Exercise Pokéwalker's exact canonical
    # 0x88 export/import boundary and both PC/history authentication layers.
    # The export hook stages only a task-3 snapshot; persisted history is not
    # observed until the retail IR state machine acknowledges status 15.
    def walker_snapshot(box: bytes) -> tuple[int, int, int, tuple[int, ...]]:
        pid, ot_id, species = box_identity(box)
        moves = tuple(box_record_payload(box)[1])
        require(
            species != 0 and all(move != 0 for move in moves),
            "Pokéwalker pending fixture is not canonical",
        )
        return pid, ot_id, species, moves

    def walker_state(
        payload: bytes,
        *,
        revision: int,
    ) -> dict[str, object]:
        require(
            len(payload) == HISTORY_FOOTER_OFFSET,
            "Pokéwalker fixture payload has the wrong size",
        )
        return {
            "payload": bytearray(payload),
            "revision": revision,
            "dirty": False,
            "pending": None,
        }

    def walker_state_fingerprint(
        state: dict[str, object],
    ) -> tuple[bytes, int, int, int, bool]:
        payload = state["payload"]
        require(
            isinstance(payload, bytearray),
            "Pokéwalker fixture history is not mutable payload bytes",
        )
        return (
            bytes(payload),
            struct.unpack_from("<H", payload, 14)[0],
            struct.unpack_from("<I", payload, 20)[0],
            int(state["revision"]),
            bool(state["dirty"]),
        )

    def walker_stage(
        state: dict[str, object],
        box: bytes,
    ) -> None:
        # Source-exact model of CaptureSnapshot: it reads only the canonical
        # owner. It does not open, allocate, touch, or dirty the history store.
        state["pending"] = walker_snapshot(box)

    def walker_discard(state: dict[str, object]) -> None:
        # The recovery wrapper calls retail restoration first, then clears the
        # resident pending-valid bit regardless of whether placement ran.
        state["pending"] = None

    def walker_ack(state: dict[str, object]) -> None:
        # Source-exact model of RecordSnapshot after successful retail status
        # 15. Clear pending first, then use task-3 allocation/LRU/append rules.
        snapshot = state["pending"]
        if snapshot is None:
            return
        state["pending"] = None
        require(
            isinstance(snapshot, tuple) and len(snapshot) == 4,
            "Pokéwalker pending snapshot is malformed",
        )
        pid, ot_id, species, moves = snapshot
        payload = state["payload"]
        require(
            isinstance(payload, bytearray)
            and isinstance(moves, tuple),
            "Pokéwalker ACK fixture state is malformed",
        )
        records = history_records(
            bytes(payload) + bytes(HISTORY_IMAGE_SIZE - len(payload))
        )
        index = next(
            (
                candidate
                for candidate, record in enumerate(records)
                if record[15] & 1
                and struct.unpack_from("<II", record) == (pid, ot_id)
            ),
            -1,
        )
        if index < 0:
            index = next(
                (
                    candidate
                    for candidate, record in enumerate(records)
                    if not (record[15] & 1)
                ),
                -1,
            )
            if index < 0:
                next_access = struct.unpack_from("<I", payload, 20)[0]
                index = max(
                    range(HISTORY_RECORD_COUNT),
                    key=lambda candidate: (
                        next_access
                        - struct.unpack_from("<I", records[candidate], 8)[0]
                    )
                    & 0xFFFFFFFF,
                )
            else:
                record_count = struct.unpack_from("<H", payload, 14)[0]
                struct.pack_into("<H", payload, 14, record_count + 1)
            record_offset = HISTORY_HEADER_SIZE + index * HISTORY_RECORD_SIZE
            payload[record_offset:record_offset + HISTORY_RECORD_SIZE] = bytes(
                HISTORY_RECORD_SIZE
            )
            next_access = (
                struct.unpack_from("<I", payload, 20)[0] + 1
            ) & 0xFFFFFFFF
            struct.pack_into("<I", payload, 20, next_access)
            struct.pack_into(
                "<IIIHBB",
                payload,
                record_offset,
                pid,
                ot_id,
                next_access,
                species,
                0,
                1,
            )
            state["dirty"] = True
            state["revision"] = int(state["revision"]) + 1

        record_offset = HISTORY_HEADER_SIZE + index * HISTORY_RECORD_SIZE
        for move in moves:
            move_count = payload[record_offset + 14]
            known = struct.unpack_from(
                f"<{move_count}H", payload, record_offset + 16
            ) if move_count else ()
            if move in known:
                continue
            require(
                move_count < 24,
                "Pokéwalker ACK fixture unexpectedly needs move eviction",
            )
            struct.pack_into(
                "<H", payload, record_offset + 16 + move_count * 2, move
            )
            payload[record_offset + 14] = move_count + 1
            struct.pack_into("<H", payload, record_offset + 12, species)
            next_access = (
                struct.unpack_from("<I", payload, 20)[0] + 1
            ) & 0xFFFFFFFF
            struct.pack_into("<I", payload, 20, next_access)
            struct.pack_into("<I", payload, record_offset + 8, next_access)
            state["dirty"] = True
            state["revision"] = int(state["revision"]) + 1

    pending_box = controlled_box_record(
        source,
        ot_id_xor=0x6E6F6E65,
        moves=(33, 45, 98, 129),
        pp=(10, 10, 10, 10),
        pp_ups=(0, 0, 0, 0),
    )
    pending_identity = box_identity(pending_box)[:2]
    require(
        history_identity_count(
            controlled_history_payload
            + bytes(HISTORY_IMAGE_SIZE - len(controlled_history_payload)),
            *pending_identity,
        )
        == 0,
        "Pokéwalker missing-record fixture identity already exists",
    )

    missing_cancel = walker_state(
        controlled_history_payload,
        revision=0x10203040,
    )
    missing_before = walker_state_fingerprint(missing_cancel)
    missing_unrelated_before = tuple(
        history_records(missing_before[0])
    )
    walker_stage(missing_cancel, pending_box)
    require(
        walker_state_fingerprint(missing_cancel) == missing_before,
        "Pokéwalker missing-record stage mutated history",
    )
    walker_discard(missing_cancel)
    missing_after = walker_state_fingerprint(missing_cancel)
    require(
        missing_after == missing_before
        and tuple(history_records(missing_after[0]))
        == missing_unrelated_before,
        "Pokéwalker missing-record cancellation changed history",
    )

    full_payload = bytearray(HISTORY_FOOTER_OFFSET)
    full_payload[:HISTORY_HEADER_SIZE] = controlled_history_payload[
        :HISTORY_HEADER_SIZE
    ]
    struct.pack_into("<H", full_payload, 14, HISTORY_RECORD_COUNT)
    struct.pack_into("<I", full_payload, 20, 0x01000000)
    for index in range(HISTORY_RECORD_COUNT):
        record_offset = HISTORY_HEADER_SIZE + index * HISTORY_RECORD_SIZE
        struct.pack_into(
            "<IIIHBBH",
            full_payload,
            record_offset,
            0x70000000 + index,
            0x71000000 + index,
            index + 1,
            1 + index % 493,
            1,
            1,
            1 + index % 467,
        )
    require(
        history_identity_count(
            bytes(full_payload) + bytes(HISTORY_IMAGE_SIZE - len(full_payload)),
            *pending_identity,
        )
        == 0,
        "Pokéwalker full-capacity fixture identity collides",
    )
    full_cancel = walker_state(bytes(full_payload), revision=0x50607080)
    full_before = walker_state_fingerprint(full_cancel)
    oldest_before = history_records(full_before[0])[0]
    unrelated_before = history_records(full_before[0])[173]
    walker_stage(full_cancel, pending_box)
    require(
        walker_state_fingerprint(full_cancel) == full_before,
        "Pokéwalker full-capacity stage mutated or evicted history",
    )
    walker_discard(full_cancel)
    full_after = walker_state_fingerprint(full_cancel)
    require(
        full_after == full_before
        and history_records(full_after[0])[0] == oldest_before
        and history_records(full_after[0])[173] == unrelated_before,
        "Pokéwalker full-capacity cancellation changed history",
    )

    acknowledged = walker_state(
        controlled_history_payload,
        revision=0x90,
    )
    ack_before = walker_state_fingerprint(acknowledged)
    ack_unrelated_before = history_records(ack_before[0])[0]
    walker_stage(acknowledged, pending_box)
    walker_ack(acknowledged)
    ack_once = walker_state_fingerprint(acknowledged)
    ack_image = ack_once[0] + bytes(HISTORY_IMAGE_SIZE - len(ack_once[0]))
    require(
        ack_once[1] == ack_before[1] + 1
        and ack_once[2] == ack_before[2] + 5
        and ack_once[3] == ack_before[3] + 5
        and ack_once[4]
        and history_identity_count(ack_image, *pending_identity) == 1
        and find_history_record(ack_image, *pending_identity)[2]
        == (33, 45, 98, 129)
        and history_records(ack_once[0])[0] == ack_unrelated_before,
        "Pokéwalker successful ACK did not record one pending baseline",
    )
    walker_ack(acknowledged)
    require(
        walker_state_fingerprint(acknowledged) == ack_once,
        "Pokéwalker duplicate status-15 ACK recorded twice",
    )

    transit = bytes(source)
    walker_export = replace_pc_slots(
        controlled_raw, {(0, BOX_TARGET_SLOT): canonical_empty}
    )
    assert_pc_transaction_diff(
        controlled_raw, walker_export, ((0, BOX_TARGET_SLOT),)
    )
    walker_recovered = replace_pc_slots(
        walker_export, {(0, BOX_TARGET_SLOT): transit}
    )
    require(
        walker_recovered == controlled_raw,
        "Pokéwalker failure recovery was not byte-exact",
    )
    walker_success = replace_pc_slots(
        controlled_raw,
        {
            (0, BOX_TARGET_SLOT): canonical_empty,
            (0, walker_slot): transit,
        },
    )
    assert_pc_transaction_diff(
        controlled_raw,
        walker_success,
        ((0, BOX_TARGET_SLOT), (0, walker_slot)),
    )
    _, walker_base = active_pc_copy(walker_success)
    require(
        pc_box_record(walker_success, walker_base, 0, walker_slot)
        == source
        and box_identity(
            pc_box_record(walker_success, walker_base, 0, walker_slot)
        )[:2]
        == source_identity
        and all(
            walker_success[offset:offset + HISTORY_IMAGE_SIZE]
            == controlled_raw[offset:offset + HISTORY_IMAGE_SIZE]
            for offset in HISTORY_MIRROR_OFFSETS
        ),
        "Pokéwalker round trip changed identity/history",
    )
    arrival_moves = (70, 71)
    arrival = controlled_box_record(
        switch,
        ot_id_xor=0xC33CC33C,
        moves=(70, 71, 0, 0),
        pp=(10, 10, 0, 0),
        pp_ups=(0, 0, 0, 0),
    )
    arrival_identity = box_identity(arrival)[:2]
    arrival_pc = replace_pc_slots(
        walker_success, {(0, arrival_slot): arrival}
    )
    arrival_payload = bytearray(controlled_history_payload)
    seed_history_record(arrival_payload, arrival, arrival_moves)
    walker_arrival = seal_history(arrival_pc, bytes(arrival_payload))
    reparsed = bytes(bytearray(walker_arrival))
    _, reparsed_base = active_pc_copy(reparsed)
    _, _, reparsed_history = selected_persisted_history(reparsed)
    boxed_checksums = validate_all_boxed_checksums(
        reparsed, reparsed_base
    )
    require(
        pc_box_record(reparsed, reparsed_base, 0, arrival_slot) == arrival
        and history_identity_count(reparsed_history, *source_identity) == 1
        and history_identity_count(reparsed_history, *arrival_identity) == 1
        and find_history_record(
            reparsed_history, *source_identity
        )[2]
        == source_history
        and find_history_record(
            reparsed_history, *arrival_identity
        )[2]
        == arrival_moves
        and len(boxed_checksums) == 900
        and all(
            valid_history_image(
                reparsed[offset:offset + HISTORY_IMAGE_SIZE], mirror
            )
            for mirror, offset in enumerate(HISTORY_MIRROR_OFFSETS)
        ),
        "Pokéwalker arrival/save-reparse authentication differs",
    )

    return {
        "evidence_kind":
            "non-probative source-exact serialization oracle",
        "actual_ui_companion":
            "retail Route 34 daycare script 9501 evidence",
        "trade": {
            "failure_save_exact": True,
            "failure_boundary":
                "staged authenticated transit rejected by occupied slot",
            "outgoing_identity": list(source_identity),
            "outgoing_history": list(source_history),
            "incoming_identity": list(incoming_identity),
            "incoming_baseline": list(incoming_moves),
            "one_record_each": True,
            "save_reparse_sha256": trade_reparse_sha256,
        },
        "form": {
            "identity": list(form_identity),
            "species": 479,
            "form": 1,
            "current_moves": list(form_after_moves),
            "history": list(form_before_moves + (315,)),
            "invalid_form_fail_closed": True,
            "save_reparse_sha256": form_reparse_sha256,
            "candidate_order_and_known_exclusion":
                "task2 builder/source-static companion",
        },
        "egg_hatch": {
            "identity": list(egg_identity),
            "pre_hatch_record_count": 0,
            "inherited_baseline": list(egg_moves),
            "parent_and_prior_slot_excluded": True,
            "save_reparse_sha256": hatch_reparse_sha256,
        },
        "pokewalker": {
            "protocol": "non-probative Python oracle; see ROM evidence",
            "export_transaction": {
                "stage_is_history_read_only": True,
                "missing_record_cancel_image_exact": True,
                "full_319_cancel_image_exact": True,
                "full_319_oldest_and_unrelated_exact": True,
                "header_count_sequence_revision_dirty_exact": True,
                "ack_commits_pending_once": True,
                "duplicate_ack_inert": True,
                "pending_identity": list(pending_identity),
                "ack_revision_delta": ack_once[3] - ack_before[3],
                "ack_access_sequence_delta": ack_once[2] - ack_before[2],
            },
            "failure_recovery_exact": True,
            "round_trip_identity": list(source_identity),
            "round_trip_history": list(source_history),
            "arrival_identity": list(arrival_identity),
            "arrival_baseline": list(arrival_moves),
        },
        "authenticated_pc_generations": len(valid_pc_copies(reparsed)),
        "all_900_boxed_checksums_valid": len(boxed_checksums) == 900,
        "both_history_mirrors_valid": True,
        "save_reparse_exact": reparsed == walker_arrival,
        "final_sha256": hashlib.sha256(reparsed).hexdigest(),
    }


def target_semantic_diff(before: bytes, after: bytes) -> list[int]:
    before_payload, _, _, _ = record_payload(before)
    after_payload, _, _, _ = record_payload(after)
    return [
        index
        for index, (old, new) in enumerate(zip(before_payload, after_payload))
        if old != new
    ]


def run(args: argparse.Namespace) -> dict:
    rom = args.rom.resolve()
    dsv = args.dsv.resolve()
    require(rom.is_file(), f"ROM not found: {rom}")
    require(dsv.is_file(), f"DSV not found: {dsv}")
    source_dsv = dsv.read_bytes()
    source_hash = hashlib.sha256(source_dsv).hexdigest()
    if args.expected_dsv_sha256:
        require(
            source_hash == args.expected_dsv_sha256.lower(),
            f"preserved DSV hash differs: {source_hash}",
        )
    immutable_raw = PARTY.extract_raw_save(dsv)
    (
        controlled_raw,
        baseline_party,
        target_pid,
        target_ot_id,
        controlled_history_payload,
        box_fixture,
    ) = make_controlled_raw(immutable_raw)
    daycare_raw, daycare_fixture = make_task6_daycare_raw(controlled_raw)
    task6_serialization_evidence = task6_serialization_surrogate_evidence(
        controlled_raw,
        controlled_history_payload,
        box_fixture,
    )
    baseline_counter, occupied, checked_party = PARTY.party_image(controlled_raw)
    require(checked_party == baseline_party, "controlled party selection differs")
    require(occupied == 5, f"fixture party count differs: {occupied}")
    baseline_summary = PARTY.summarize_party(baseline_party)
    baseline_checksums = validate_all_party_checksums(baseline_party)
    controlled_pc_counter, controlled_pc_base = active_pc_copy(controlled_raw)
    baseline_box_checksums = validate_all_boxed_checksums(
        controlled_raw, controlled_pc_base
    )
    baseline_target_box = pc_box_record(
        controlled_raw, controlled_pc_base, 0, BOX_TARGET_SLOT
    )
    baseline_switch_box = pc_box_record(
        controlled_raw, controlled_pc_base, 0, BOX_SWITCH_SLOT
    )
    require(
        baseline_target_box == box_fixture["target"]
        and baseline_switch_box == box_fixture["switch"],
        "controlled active boxed records differ from fixture metadata",
    )
    require(
        baseline_summary[4]["shiny"] is True
        and baseline_summary[4]["species"] == 16,
        "fixture shiny Pidgey is missing or invalid",
    )
    before_target = party_record(baseline_party, TARGET_SLOT)
    before_payload, before_moves, before_pp, before_pp_ups = record_payload(
        before_target
    )
    require(
        before_moves == CONTROLLED_MOVES
        and before_pp[TARGET_REPLACEMENT_SLOT] == 1
        and before_pp_ups[TARGET_REPLACEMENT_SLOT] == 2,
        "controlled Tentacool PP/PP-Up precondition differs",
    )

    args.screenshot_dir.mkdir(parents=True, exist_ok=True)
    args.export_raw.parent.mkdir(parents=True, exist_ok=True)
    args.controlled_raw.parent.mkdir(parents=True, exist_ok=True)
    args.controlled_raw.write_bytes(controlled_raw)
    args.daycare_raw.parent.mkdir(parents=True, exist_ok=True)
    args.daycare_raw.write_bytes(daycare_raw)
    captures: list[str] = []
    state_evidence: list[dict[str, int | str]] = []
    transition_evidence: list[dict[str, object]] = []
    boundary_evidence: list[dict[str, object]] = []
    prospective_evidence: list[dict[str, object]] = []
    control_pixel_evidence: list[dict[str, object]] = []
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    # Main acceptance: every touch/key transition is asserted immediately.
    with HEADLESS.silence_native_output(True):
        emu, imported = new_emulator(rom, controlled_raw)
        try:
            boot_party, _ = PARTY.wait_for_runtime_party(
                emu,
                baseline_party,
                maximum_frames=90,
            )
            require(
                boot_party == baseline_party,
                "boot changed one or more serialized party records",
            )
            captures.append(
                screenshot(emu, args.screenshot_dir, "00_visible_boot.png")
            )

            open_summary_moves(emu, TARGET_SLOT)
            captures.append(
                screenshot(emu, args.screenshot_dir, "01_moves_prompt.png")
            )
            baseline_runtime_party = wait_party_locked(emu)
            baseline_metadata, baseline_history = runtime_history(emu)
            history_index, baseline_history_record, history_moves_before = (
                find_history_record(
                    baseline_history,
                    target_pid,
                    target_ot_id,
                )
            )
            revision_before = struct.unpack_from("<I", baseline_metadata, 8)[0]
            dirty_before = baseline_metadata[4]
            require(dirty_before == 0, "controlled history baseline is not clean")
            require(
                history_moves_before == CONTROLLED_HISTORY_MOVES,
                "controlled history acquisition order differs",
            )

            # Touch entry and full candidate PP presentation.
            inactive_state = locate_inactive_summary_state(emu)
            touch(emu, 40, 176, 40)
            transition_evidence.append(
                inactive_summary_evidence(
                    emu,
                    inactive_state,
                    "left page icon is not a relearn action",
                )
            )
            assert_cancel_exact(
                emu,
                baseline_runtime_party,
                baseline_metadata,
                baseline_history,
                "non-action page icon touch",
            )
            # The vanilla page icon may navigate normally; return to Moves.
            tap(emu, "RIGHT", 80)
            require(
                read_u8(
                    emu,
                    inactive_state
                    - SUMMARY_STATE_RETAIL_SIZE
                    + SUMMARY_PAGE_MODE_OFFSET,
                )
                == 1,
                "vanilla page navigation did not return to Moves",
            )
            touch(emu, 40, 140, 80)
            summary_state = locate_summary_relearn_state(emu)
            state_evidence.append(
                summary_state_evidence(
                    emu,
                    summary_state,
                    1,
                    0,
                    "candidate list",
                )
            )
            initial_view = assert_candidate_viewport(
                emu, summary_state, 0, 0, "initial candidate list"
            )
            require(
                initial_view["count"] > 4,
                "controlled fixture does not exceed four visible candidates",
            )
            require(
                TARGET_MOVE in initial_view["candidates"],
                "controlled target move is not relearnable",
            )
            target_candidate_index = initial_view["candidates"].index(
                TARGET_MOVE
            )
            candidate_capture = Path(
                screenshot(
                    emu,
                    args.screenshot_dir,
                    "02_candidate_list_full_pp.png",
                )
            )
            captures.append(str(candidate_capture))
            pp_pixel_evidence = assert_pp_pixels(candidate_capture)
            control_pixel_evidence.append(
                assert_control_pixels(
                    candidate_capture,
                    label="candidate Pick/Back glyph boundaries",
                    a_span=(8, 40),
                    gap_span=(40, 44),
                    b_span=(44, 49),
                )
            )

            # Exact exclusive edges: x40..43 are blank; x44 is Back.
            for x in (40, 43):
                touch(emu, x, 140, 20)
                transition_evidence.append(
                    summary_state_evidence(
                        emu,
                        summary_state,
                        1,
                        0,
                        f"touch list dead gap x{x}",
                    )
                )
                assert_cancel_exact(
                    emu,
                    baseline_runtime_party,
                    baseline_metadata,
                    baseline_history,
                    f"list dead-gap touch x{x}",
                )
            touch(emu, 44, 140, 20)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 0, 0, "touch list Back glyph edge x44"
                )
            )
            assert_cancel_exact(
                emu,
                baseline_runtime_party,
                baseline_metadata,
                baseline_history,
                "list Back glyph-edge cancellation",
            )

            # Blue Cancel from the list is exact and non-mutating.
            touch(emu, 40, 140, 30)
            touch(emu, 220, 176, 60)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 0, 0, "touch list Cancel"
                )
            )
            assert_cancel_exact(
                emu,
                baseline_runtime_party,
                baseline_metadata,
                baseline_history,
                "touch candidate-list cancellation",
            )

            # Prompt touch -> list, Pick strip -> slot, Back strip -> list.
            touch(emu, 40, 140, 60)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 1, 0, "touch prompt entry"
                )
            )
            touch(emu, 39, 140, 30)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 3, 0, "touch list Pick edge x39"
                )
            )
            for x in (40, 43):
                touch(emu, x, 140, 20)
                transition_evidence.append(
                    summary_state_evidence(
                        emu,
                        summary_state,
                        3,
                        0,
                        f"touch slot dead gap x{x}",
                    )
                )
            touch(emu, 44, 140, 30)
            transition_evidence.append(
                summary_state_evidence(
                    emu,
                    summary_state,
                    1,
                    0,
                    "touch slot Back glyph edge x44",
                )
            )
            assert_cancel_exact(
                emu,
                baseline_runtime_party,
                baseline_metadata,
                baseline_history,
                "slot-to-list cancellation",
            )

            # Candidate row -> slot, HM row -> blocked; all visible dismissal
            # controls return to the slot without mutation.
            touch(emu, 50, 24, 60)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 3, 0, "touch candidate row"
                )
            )
            touch(emu, 50, 24, 60)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 5, 0, "touch HM-protected slot"
                )
            )
            hm_capture = Path(
                screenshot(emu, args.screenshot_dir, "03_hm_blocked.png")
            )
            captures.append(str(hm_capture))
            control_pixel_evidence.append(
                assert_control_pixels(
                    hm_capture,
                    label="HM OK/Back glyph boundaries",
                    a_span=(8, 31),
                    gap_span=(31, 35),
                    b_span=(35, 40),
                )
            )
            assert_cancel_exact(
                emu,
                baseline_runtime_party,
                baseline_metadata,
                baseline_history,
                "HM-protected rejection",
            )
            touch(emu, 20, 140, 30)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 3, 0, "touch HM A:OK dismissal"
                )
            )
            touch(emu, 50, 24, 20)
            summary_state_evidence(
                emu, summary_state, 5, 0, "touch HM row for Back probe"
            )
            touch(emu, 35, 140, 30)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 3, 0, "touch HM B:Back edge x35"
                )
            )
            touch(emu, 50, 24, 20)
            summary_state_evidence(
                emu, summary_state, 5, 0, "touch HM row for blue Cancel"
            )
            touch(emu, 220, 176, 30)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 3, 0, "touch HM blue Cancel"
                )
            )
            touch(emu, 44, 140, 30)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 1, 0, "touch slot Back after HM"
                )
            )
            touch(emu, 44, 140, 30)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 0, 0, "touch list Back after HM"
                )
            )
            assert_cancel_exact(
                emu,
                baseline_runtime_party,
                baseline_metadata,
                baseline_history,
                "HM flow cancellation",
            )

            # Scroll through the four-row viewport with immediate bounds checks.
            touch(emu, 40, 140, 50)
            scroll_views: list[dict[str, object]] = []
            for cursor, top in ((1, 0), (2, 0), (3, 0), (4, 1)):
                tap(emu, "DOWN", 20)
                scroll_views.append(
                    assert_candidate_viewport(
                        emu, summary_state, cursor, top, f"scroll {cursor}"
                    )
                )
            captures.append(
                screenshot(emu, args.screenshot_dir, "04_candidate_scrolled.png")
            )
            for cursor, top in ((3, 1), (2, 1), (1, 1), (0, 0)):
                tap(emu, "UP", 20)
                scroll_views.append(
                    assert_candidate_viewport(
                        emu, summary_state, cursor, top, f"reverse scroll {cursor}"
                    )
                )

            # Navigate directly to the controlled learnset target.
            target_view = initial_view
            for cursor in range(1, target_candidate_index + 1):
                tap(emu, "DOWN", 20)
                top = 0 if cursor < 4 else cursor - 3
                target_view = assert_candidate_viewport(
                    emu,
                    summary_state,
                    cursor,
                    top,
                    f"target navigation {cursor}",
                )
            target_row_y = 24 + 32 * (
                target_view["cursor"] - target_view["top"]
            )

            # Row select -> slot 3 -> confirmation; Back is immediate/exact.
            touch(emu, 50, target_row_y, 40)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 3, 0, "touch candidate before confirm"
                )
            )
            prospective_evidence.append(
                assert_prospective_slot(
                    emu, summary_state, 0, "inline preview before slot choice"
                )
            )
            touch(emu, 50, 120, 40)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 4, 0, "touch replacement slot"
                )
            )
            confirmation_capture = Path(
                screenshot(emu, args.screenshot_dir, "05_confirmation.png")
            )
            captures.append(str(confirmation_capture))
            control_pixel_evidence.append(
                assert_control_pixels(
                    confirmation_capture,
                    label="confirmation OK/Back glyph boundaries",
                    a_span=(8, 31),
                    gap_span=(31, 35),
                    b_span=(35, 40),
                )
            )
            prospective_evidence.append(
                assert_prospective_slot(
                    emu, summary_state, 3, "inline preview at confirmation"
                )
            )
            for x in (31, 34):
                touch(emu, x, 140, 20)
                transition_evidence.append(
                    summary_state_evidence(
                        emu,
                        summary_state,
                        4,
                        0,
                        f"touch confirmation dead gap x{x}",
                    )
                )
                assert_cancel_exact(
                    emu,
                    baseline_runtime_party,
                    baseline_metadata,
                    baseline_history,
                    f"confirmation dead-gap touch x{x}",
                )
            touch(emu, 35, 140, 30)
            transition_evidence.append(
                summary_state_evidence(
                    emu,
                    summary_state,
                    3,
                    0,
                    "touch confirmation Back glyph edge x35",
                )
            )
            assert_cancel_exact(
                emu,
                baseline_runtime_party,
                baseline_metadata,
                baseline_history,
                "confirmation-to-slot cancellation",
            )
            touch(emu, 44, 140, 30)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 1, 0, "touch slot Back after confirm"
                )
            )
            assert_cancel_exact(
                emu,
                baseline_runtime_party,
                baseline_metadata,
                baseline_history,
                "confirmation cancellation at list",
            )

            # Re-select and touch OK. This is the first permanent mutation.
            touch(emu, 50, target_row_y, 40)
            touch(emu, 50, 120, 40)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 4, 0, "confirmation before touch OK"
                )
            )
            touch(emu, 20, 140, 90)
            captures.append(
                screenshot(emu, args.screenshot_dir, "06_success.png")
            )
            committed_party = wait_party_locked(emu)
            committed_target = party_record(committed_party, TARGET_SLOT)
            _, committed_moves, committed_pp, committed_pp_ups = record_payload(
                committed_target
            )
            require(
                committed_moves == (57, 48, 352, TARGET_MOVE),
                f"confirmed replacement differs: {committed_moves}",
            )
            require(
                committed_pp[TARGET_REPLACEMENT_SLOT] == 8
                and committed_pp_ups[TARGET_REPLACEMENT_SLOT] == 0,
                "replacement PP/PP Ups do not match normal replacement",
            )
            committed_metadata, committed_history = runtime_history(emu)
            state_evidence.append(
                summary_state_evidence(
                    emu,
                    summary_state,
                    6,
                    1,
                    "successful replacement",
                )
            )
            revision_after = struct.unpack_from("<I", committed_metadata, 8)[0]
            dirty_after = committed_metadata[4]
            require(dirty_after == 1, "successful replacement did not dirty history")
            require(
                revision_after > revision_before,
                "successful replacement did not advance history revision",
            )
            new_index, new_history_record, history_moves_after = (
                find_history_record(
                    committed_history,
                    target_pid,
                    target_ot_id,
                )
            )
            require(new_index == history_index, "replacement changed history identity")
            require(
                history_moves_after[:len(history_moves_before)]
                == history_moves_before,
                "replacement reordered prior move history",
            )
            require(
                history_moves_after.count(TARGET_MOVE) == 1,
                "replacement history lacks exactly one confirmed move",
            )
            for index, (old, new) in enumerate(
                zip(
                    history_records(baseline_history),
                    history_records(committed_history),
                )
            ):
                if index != history_index:
                    require(old == new, f"history record {index} changed unexpectedly")

            touch(emu, 220, 176, 80)
            transition_evidence.append(
                summary_state_evidence(
                    emu, summary_state, 0, 1, "touch success blue Cancel"
                )
            )
            captures.append(
                screenshot(emu, args.screenshot_dir, "07_replaced_move_pp.png")
            )
            normal_save(emu, baseline_counter)
            captures.append(
                screenshot(emu, args.screenshot_dir, "08_after_save.png")
            )
            export_backup_artifact(emu, args.export_raw)
        finally:
            close_emulator(emu, imported)

    # A separate no-touch path proves the documented modal X/A/B controls.
    key_capture = args.screenshot_dir / "09_key_only_scenario.png"
    key_only_evidence = isolated_scenario_evidence(
        rom,
        args.controlled_raw,
        "keys",
        key_capture,
    )
    captures.append(str(key_capture))

    party_switch_capture = (
        args.screenshot_dir / "09_party_real_switching.png"
    )
    party_switch_evidence = isolated_scenario_evidence(
        rom,
        args.controlled_raw,
        "party_switch",
        party_switch_capture,
    )
    captures.append(str(party_switch_capture))

    party_fail_closed_capture = (
        args.screenshot_dir / "09_party_fail_closed.png"
    )
    party_fail_closed_evidence = isolated_scenario_evidence(
        rom,
        args.controlled_raw,
        "party_fail_closed",
        party_fail_closed_capture,
    )
    captures.append(str(party_fail_closed_capture))

    center_bootstrap_capture = (
        args.screenshot_dir / "10_retail_center_bootstrap.png"
    )
    center_bootstrap_evidence = isolated_scenario_evidence(
        rom,
        args.controlled_raw,
        "center_bootstrap",
        center_bootstrap_capture,
    )
    captures.append(str(center_bootstrap_capture))
    terminal_bootstrap_capture = (
        args.screenshot_dir / "11_retail_terminal_bootstrap.png"
    )
    terminal_bootstrap_evidence = isolated_scenario_evidence(
        rom,
        artifact_path(center_bootstrap_evidence["exported_raw_save"]),
        "terminal_bootstrap",
        terminal_bootstrap_capture,
    )
    captures.append(str(terminal_bootstrap_capture))

    pc_fail_closed_capture = (
        args.screenshot_dir / "11_pc_fail_closed.png"
    )
    pc_fail_closed_evidence = isolated_scenario_evidence(
        rom,
        artifact_path(terminal_bootstrap_evidence["exported_raw_save"]),
        "pc_fail_closed",
        pc_fail_closed_capture,
    )
    captures.append(str(pc_fail_closed_capture))
    pc_teardown_capture = (
        args.screenshot_dir / "11_pc_nested_lifecycle.png"
    )
    pc_teardown_evidence = isolated_scenario_evidence(
        rom,
        artifact_path(terminal_bootstrap_evidence["exported_raw_save"]),
        "pc_teardown",
        pc_teardown_capture,
    )
    captures.extend(pc_teardown_evidence["captures"])

    boxed_capture = args.screenshot_dir / "12_actual_boxed_summary.png"
    boxed_evidence = isolated_scenario_evidence(
        rom,
        artifact_path(terminal_bootstrap_evidence["exported_raw_save"]),
        "boxed",
        boxed_capture,
    )
    captures.extend(boxed_evidence["captures"])
    boxed_reload_capture = (
        args.screenshot_dir / "13_actual_boxed_reload.png"
    )
    boxed_reload_evidence = isolated_scenario_evidence(
        rom,
        artifact_path(boxed_evidence["exported_raw_save"]),
        "boxed_reload",
        boxed_reload_capture,
    )
    captures.extend(boxed_reload_evidence["captures"])
    transfer_capture = (
        args.screenshot_dir / "14_retail_box_party_box_transfer.png"
    )
    transfer_evidence = isolated_scenario_evidence(
        rom,
        artifact_path(boxed_evidence["exported_raw_save"]),
        "transfer",
        transfer_capture,
    )
    captures.extend(transfer_evidence["captures"])
    transfer_reload_capture = (
        args.screenshot_dir / "15_retail_transfer_reload.png"
    )
    transfer_reload_evidence = isolated_scenario_evidence(
        rom,
        artifact_path(transfer_evidence["exported_raw_save"]),
        "transfer_reload",
        transfer_reload_capture,
    )
    captures.extend(transfer_reload_evidence["captures"])
    daycare_cancel_capture = (
        args.screenshot_dir / "16_actual_daycare_cancel.png"
    )
    daycare_cancel_evidence = isolated_scenario_evidence(
        rom,
        args.daycare_raw,
        "task6_daycare_cancel",
        daycare_cancel_capture,
    )
    captures.append(daycare_cancel_evidence["capture"])
    daycare_sanitize_capture = (
        args.screenshot_dir / "17_actual_daycare_sanitize.png"
    )
    daycare_sanitize_evidence = isolated_scenario_evidence(
        rom,
        args.daycare_raw,
        "task6_daycare_sanitize",
        daycare_sanitize_capture,
    )
    captures.append(daycare_sanitize_evidence["capture"])
    daycare_exported_path = artifact_path(
        daycare_sanitize_evidence["exported_raw_save"]
    )
    require(
        hashlib.sha256(
            PARTY.extract_raw_save(daycare_exported_path)
        ).hexdigest()
        == daycare_sanitize_evidence["exported_raw_sha256"],
        "retail daycare export differs before reload child launch",
    )
    daycare_reload_capture = (
        args.screenshot_dir / "18_actual_daycare_reload.png"
    )
    daycare_reload_evidence = isolated_scenario_evidence(
        rom,
        daycare_exported_path,
        "task6_daycare_reload",
        daycare_reload_capture,
    )
    captures.append(daycare_reload_evidence["capture"])
    pokewalker_rom_capture = (
        args.screenshot_dir / "19_packaged_pokewalker_transaction.png"
    )
    pokewalker_rom_evidence = isolated_scenario_evidence(
        rom,
        args.controlled_raw,
        "task6_pokewalker_rom",
        pokewalker_rom_capture,
    )
    captures.append(pokewalker_rom_evidence["capture"])

    # Each extra boundary/lifecycle scenario runs in a fresh emulator process.
    for scenario in ("empty", "identity", "position", "teardown"):
        scenario_capture = (
            args.screenshot_dir / f"09_{scenario}_scenario.png"
        )
        boundary_evidence.append(
            isolated_scenario_evidence(
                rom,
                args.controlled_raw,
                scenario,
                scenario_capture,
            )
        )
        captures.append(str(scenario_capture))

    # A fresh process also selects the unchanged controlled baseline exactly;
    # the teardown subprocess itself already proves two real unloads/reloads.
    teardown_probe_path = args.screenshot_dir / "09_teardown_reload.png"
    controlled_probe_party, controlled_probe_metadata, controlled_probe_history = (
        fresh_reload_evidence(
            rom,
            args.controlled_raw,
            teardown_probe_path,
        )
    )
    captures.append(str(teardown_probe_path))
    _, _, selected_controlled_history = selected_persisted_history(controlled_raw)
    require(
        controlled_probe_party == baseline_party
        and controlled_probe_metadata[4] == 0
        and controlled_probe_history == selected_controlled_history,
        "post-lifecycle fresh boot changed persisted party/history",
    )
    boundary_evidence.append(
        {
            "label": "post-lifecycle fresh boot",
            "party_exact": True,
            "history_exact": True,
            "dirty": controlled_probe_metadata[4],
        }
    )

    saved_raw = PARTY.extract_raw_save(args.export_raw)
    saved_counter, saved_count, saved_party = PARTY.party_image(saved_raw)
    saved_pc_counter, saved_pc_base = active_pc_copy(saved_raw)
    saved_box_checksums = validate_all_boxed_checksums(
        saved_raw, saved_pc_base
    )
    baseline_pc_image = controlled_raw[
        controlled_pc_base + PC_SAVE_OFFSET:
        controlled_pc_base + PC_SAVE_OFFSET + PC_STORAGE_BOXES_SIZE
    ]
    saved_pc_image = saved_raw[
        saved_pc_base + PC_SAVE_OFFSET:
        saved_pc_base + PC_SAVE_OFFSET + PC_STORAGE_BOXES_SIZE
    ]
    require(
        saved_pc_image == baseline_pc_image,
        "party-only acceptance changed one or more serialized PC records",
    )
    require(saved_count == occupied, "save changed occupied party count")
    require(
        PARTY.save_counter_compare(saved_counter, baseline_counter) > 0,
        "save counter did not advance",
    )
    saved_summary = PARTY.summarize_party(saved_party)
    saved_checksums = validate_all_party_checksums(saved_party)
    require(
        saved_summary[4] == baseline_summary[4]
        and saved_summary[4]["shiny"] is True,
        "shiny Pidgey identity/checksum changed",
    )
    saved_target = party_record(saved_party, TARGET_SLOT)
    _, saved_moves, saved_pp, saved_pp_ups = record_payload(saved_target)
    require(
        saved_moves == (57, 48, 352, TARGET_MOVE)
        and saved_pp[TARGET_REPLACEMENT_SLOT] == 8
        and saved_pp_ups[TARGET_REPLACEMENT_SLOT] == 0,
        "saved replacement move/PP/PP Ups differ",
    )
    require(
        saved_party[:8] == baseline_party[:8],
        "party header changed unexpectedly",
    )
    for index in range(6):
        if index != TARGET_SLOT:
            require(
                party_record(saved_party, index)
                == party_record(baseline_party, index),
                f"unrelated serialized party record {index} changed",
            )
    require(
        saved_target[0x88:] == before_target[0x88:],
        "unrelated target PartyPokemon battle/stat bytes changed",
    )
    semantic_differences = target_semantic_diff(before_target, saved_target)
    attacks = PARTY.SUBSTRUCT_OFFSETS[
        (struct.unpack_from("<I", before_target)[0] & 0x3E000) >> 13
    ][1]
    allowed_differences = {
        attacks + TARGET_REPLACEMENT_SLOT * 2,
        attacks + TARGET_REPLACEMENT_SLOT * 2 + 1,
        attacks + 8 + TARGET_REPLACEMENT_SLOT,
        attacks + 12 + TARGET_REPLACEMENT_SLOT,
    }
    require(
        set(semantic_differences) <= allowed_differences,
        "unrelated decrypted target bytes changed: "
        + ",".join(f"0x{offset:X}" for offset in semantic_differences),
    )

    selected_counter, selected_mirror, persisted_history = (
        selected_persisted_history(saved_raw)
    )
    require(
        selected_counter == saved_counter,
        "persisted history generation does not match normal save generation",
    )
    persisted_index, persisted_record, persisted_moves = find_history_record(
        persisted_history,
        target_pid,
        target_ot_id,
    )
    require(
        persisted_index == history_index
        and persisted_moves == history_moves_after
        and persisted_record == new_history_record,
        "persisted target history record differs from committed runtime record",
    )
    for index, (old, new) in enumerate(
        zip(
            history_records(baseline_history),
            history_records(persisted_history),
        )
    ):
        if index != history_index:
            require(old == new, f"persisted unrelated history record {index} changed")

    reload_screenshot = args.screenshot_dir / "10_saved_reload.png"
    reloaded_party, reloaded_metadata, reloaded_history = fresh_reload_evidence(
        rom,
        args.export_raw,
        reload_screenshot,
    )
    captures.append(str(reload_screenshot))
    require(reloaded_party == saved_party, "fresh reload changed saved party bytes")
    require(
        reloaded_metadata[4] == 0,
        "fresh reload did not select a clean authenticated history baseline",
    )
    require(
        reloaded_history == persisted_history,
        "fresh reload history differs from selected persisted mirror",
    )
    _, reloaded_record, reloaded_moves = find_history_record(
        reloaded_history,
        target_pid,
        target_ot_id,
    )
    require(
        reloaded_record == persisted_record
        and reloaded_moves == persisted_moves,
        "fresh reload target history revision/record differs",
    )
    reloaded_checksums = validate_all_party_checksums(reloaded_party)
    require(
        hashlib.sha256(dsv.read_bytes()).hexdigest() == source_hash,
        "preserved source DSV was mutated",
    )

    return {
        "rom": str(rom),
        "rom_sha256": hashlib.sha256(rom.read_bytes()).hexdigest(),
        "preserved_dsv": str(dsv),
        "preserved_dsv_sha256": source_hash,
        "source_dsv_unchanged": dsv.read_bytes() == source_dsv,
        "controlled_fixture": {
            "derivation": "temporary authenticated raw save; source DSV immutable",
            "path": str(args.controlled_raw),
            "history_dirty": dirty_before,
            "history_mirrors_valid": [
                valid_history_image(
                    controlled_raw[
                        offset:offset + HISTORY_IMAGE_SIZE
                    ],
                    mirror,
                )
                for mirror, offset in enumerate(HISTORY_MIRROR_OFFSETS)
            ],
            "moves": list(before_moves),
            "pp": list(before_pp),
            "pp_ups": list(before_pp_ups),
            "pc_generation": controlled_pc_counter,
            "pc_copies_authenticated": len(valid_pc_copies(controlled_raw)),
            "boxed_target_identity": list(
                box_fixture["target_identity"]
            ),
            "boxed_switch_identity": list(
                box_fixture["switch_identity"]
            ),
            "all_900_box_checksums_valid": len(baseline_box_checksums) == 900,
        },
        "task6_daycare_fixture": {
            "path": str(args.daycare_raw),
            "sha256": hashlib.sha256(daycare_raw).hexdigest(),
            "normal_copies_authenticated": len(
                PARTY.valid_normal_copies(daycare_raw)
            ),
            "party_identity": list(daycare_fixture["party_identity"]),
            "deposited_identity": list(
                daycare_fixture["deposited_identity"]
            ),
            "history_records_seeded": [
                daycare_fixture["party_history_index"],
                daycare_fixture["deposited_history_index"],
            ],
        },
        "baseline_save_counter": baseline_counter,
        "saved_save_counter": saved_counter,
        "candidate_navigation": {
            "count": initial_view["count"],
            "ordered": list(initial_view["candidates"]),
            "viewport_scroll_proven": True,
            "views": scroll_views,
            "live_full_pp": {
                "current": list(initial_view["cache_cur_pp"]),
                "maximum": list(initial_view["cache_max_pp"]),
            },
            "pixel_evidence": pp_pixel_evidence,
        },
        "cancel_paths_exact": [
            "candidate list touch Cancel",
            "slot to list",
            "confirmation to slot",
            "HM rejection",
            "empty list",
            "identity boundary",
            "position boundary",
            "real Summary exit, overlay unload/reload, and second exit",
        ],
        "replacement": {
            "party_slot": TARGET_SLOT,
            "species": TARGET_SPECIES,
            "move_slot": TARGET_REPLACEMENT_SLOT,
            "before_moves": list(before_moves),
            "after_moves": list(saved_moves),
            "after_pp": list(saved_pp),
            "after_pp_ups": list(saved_pp_ups),
            "semantic_changed_payload_offsets": semantic_differences,
        },
        "history": {
            "record_index": history_index,
            "revision_before": revision_before,
            "revision_after_commit": revision_after,
            "moves_before": list(history_moves_before),
            "moves_after": list(history_moves_after),
            "dirty_before": dirty_before,
            "dirty_after_commit": dirty_after,
            "unrelated_records_exact": True,
            "persisted_mirror": selected_mirror,
            "persisted_counter": selected_counter,
            "persisted_record_exact": True,
            "fresh_reload_dirty": reloaded_metadata[4],
            "fresh_reload_record_exact": True,
        },
        "party": {
            "serialized_stride": "0xEC",
            "all_six_checksum_valid": True,
            "baseline_checksums": baseline_checksums,
            "saved_checksums": saved_checksums,
            "reloaded_checksums": reloaded_checksums,
            "unrelated_records_exact": True,
            "fresh_reload_exact": True,
            "shiny_pidgey": saved_summary[4],
        },
        "pc_storage": {
            "serialized_box_stride": "0x1000",
            "serialized_box_mon_stride": "0x88",
            "baseline_generation": controlled_pc_counter,
            "saved_generation": saved_pc_counter,
            "both_baseline_copies_authenticated": True,
            "all_900_baseline_checksums_valid": len(
                baseline_box_checksums
            ) == 900,
            "all_900_saved_checksums_valid": len(saved_box_checksums) == 900,
            "party_only_path_records_exact": True,
        },
        "summary_state_evidence": state_evidence,
        "immediate_touch_transitions": transition_evidence,
        "boundary_evidence": boundary_evidence,
        "key_only_evidence": key_only_evidence,
        "party_switch_evidence": party_switch_evidence,
        "party_fail_closed_evidence": party_fail_closed_evidence,
        "retail_center_bootstrap_evidence": center_bootstrap_evidence,
        "retail_terminal_bootstrap_evidence": terminal_bootstrap_evidence,
        "pc_fail_closed_evidence": pc_fail_closed_evidence,
        "pc_teardown_evidence": pc_teardown_evidence,
        "boxed_evidence": boxed_evidence,
        "boxed_reload_evidence": boxed_reload_evidence,
        "transfer_evidence": transfer_evidence,
        "transfer_reload_evidence": transfer_reload_evidence,
        "task6_daycare_cancel_evidence": daycare_cancel_evidence,
        "task6_daycare_sanitize_evidence": daycare_sanitize_evidence,
        "task6_daycare_reload_evidence": daycare_reload_evidence,
        "task6_pokewalker_rom_evidence": pokewalker_rom_evidence,
        "task6_serialization_surrogate_evidence":
            task6_serialization_evidence,
        "prospective_evidence": prospective_evidence,
        "control_pixel_evidence": control_pixel_evidence,
        "screenshots": captures,
        "exported_raw_save": str(args.export_raw),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=REPO / "test.nds")
    parser.add_argument(
        "--publication-manifest",
        type=Path,
        default=REPO / "build/pokemon_move_history_capture_build.json",
    )
    parser.add_argument("--expected-publication-manifest-sha256")
    parser.add_argument("--expected-runtime-launcher-sha256")
    parser.add_argument("--expected-runtime-verifier-sha256")
    parser.add_argument("--dsv", type=Path)
    parser.add_argument("--expected-dsv-sha256")
    parser.add_argument("--result-json", type=Path)
    parser.add_argument("--probe-raw", type=Path)
    parser.add_argument("--expected-probe-raw-sha256")
    parser.add_argument(
        "--scenario",
        choices=(
            "empty",
            "identity",
            "position",
            "teardown",
            "keys",
            "party_switch",
            "party_fail_closed",
            "pc_fail_closed",
            "pc_teardown",
            "center_bootstrap",
            "terminal_bootstrap",
            "transfer",
            "transfer_reload",
            "task6_daycare_cancel",
            "task6_daycare_sanitize",
            "task6_daycare_reload",
            "task6_pokewalker_rom",
            "boxed",
            "boxed_reload",
        ),
    )
    parser.add_argument(
        "--probe-screenshot",
        type=Path,
        default=REPO
        / "build/diagnostics/task4_summary_relearn/reload-probe.png",
    )
    parser.add_argument(
        "--screenshot-dir",
        type=Path,
        default=REPO / "build/diagnostics/task4_summary_relearn",
    )
    parser.add_argument(
        "--export-raw",
        type=Path,
        default=REPO / "build/diagnostics/task4_summary_relearn/post-save.sav",
    )
    parser.add_argument(
        "--controlled-raw",
        type=Path,
        default=REPO
        / "build/diagnostics/task4_summary_relearn/controlled-baseline.sav",
    )
    parser.add_argument(
        "--daycare-raw",
        type=Path,
        default=REPO
        / "build/diagnostics/task4_summary_relearn/"
        "task6-daycare-baseline.sav",
    )
    return parser.parse_args()


if __name__ == "__main__":
    resolved_result: Path | None = None
    try:
        arguments = parse_args()
        resolved_result = (
            arguments.result_json.resolve()
            if arguments.result_json is not None
            else None
        )
        if arguments.result_json is not None:
            require(
                str(resolved_result)
                in BOOTSTRAP_INVALIDATED_RESULTS,
                "result target was not invalidated by runtime launcher",
            )
        resolved_rom = arguments.rom.resolve()
        resolved_manifest = arguments.publication_manifest.resolve()
        EVIDENCE_ARTIFACTS.protect(
            resolved_rom,
            resolved_manifest,
            resolved_result,
            arguments.dsv.resolve() if arguments.dsv is not None else None,
            (
                arguments.probe_raw.resolve()
                if arguments.probe_raw is not None
                else None
            ),
            arguments.controlled_raw.resolve(),
            arguments.daycare_raw.resolve(),
        )
        authentication = artifact_authentication(
            resolved_rom,
            resolved_manifest,
        )
        validate_expected_authentication(
            authentication,
            expected_manifest_sha256=(
                arguments.expected_publication_manifest_sha256
            ),
            expected_launcher_sha256=(
                arguments.expected_runtime_launcher_sha256
            ),
            expected_verifier_sha256=(
                arguments.expected_runtime_verifier_sha256
            ),
        )
        SUBPROCESS_AUTHENTICATION_ARGS.extend(
            (
                "--publication-manifest",
                str(resolved_manifest),
                "--expected-publication-manifest-sha256",
                str(authentication["publication_manifest"]["sha256"]),
                "--expected-runtime-launcher-sha256",
                str(authentication["runtime_launcher"]["sha256"]),
                "--expected-runtime-verifier-sha256",
                str(authentication["runtime_verifier"]["sha256"]),
            )
        )
        if arguments.scenario is not None:
            require(arguments.probe_raw is not None, "--probe-raw is required")
            require(
                arguments.expected_probe_raw_sha256 is not None,
                "--expected-probe-raw-sha256 is required",
            )
            result = run_isolated_scenario(
                resolved_rom,
                arguments.probe_raw.resolve(),
                arguments.expected_probe_raw_sha256,
                arguments.scenario,
                arguments.probe_screenshot.resolve(),
            )
            final_probe_hash = hashlib.sha256(
                arguments.probe_raw.read_bytes()
            ).hexdigest()
            require(
                final_probe_hash == arguments.expected_probe_raw_sha256,
                "controlled raw changed during isolated execution",
            )
            result["probe_raw_sha256"] = final_probe_hash
        elif arguments.probe_raw is not None:
            result = run_reload_probe(
                resolved_rom,
                arguments.probe_raw.resolve(),
                arguments.probe_screenshot.resolve(),
            )
        else:
            require(arguments.dsv is not None, "--dsv is required")
            result = run(arguments)
        final_authentication = artifact_authentication(
            resolved_rom,
            resolved_manifest,
        )
        require(
            final_authentication == authentication,
            "runtime artifact authentication changed during execution",
        )
        result["artifact_authentication"] = final_authentication
        result = authenticate_result(result)
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if resolved_result is not None:
            write_result_atomic(resolved_result, rendered)
        sys.stdout.write(rendered)
        sys.stdout.flush()
        EVIDENCE_ARTIFACTS.reauthenticate()
        require(
            BOOTSTRAP_REAUTHENTICATE() == BOOTSTRAP_AUTHENTICATION,
            "runtime closure changed after stdout publication",
        )
    except Exception as error:
        if resolved_result is not None and resolved_result.exists():
            resolved_result.unlink()
            _fsync_directory(resolved_result.parent)
        print(f"Summary relearn runtime verification failed: {error}", file=sys.stderr)
        raise SystemExit(1)
