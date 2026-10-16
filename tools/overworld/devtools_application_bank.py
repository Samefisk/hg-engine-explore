"""Decode authenticated behavior-bank provenance without treating local bits as IDs."""

from __future__ import annotations

import json
from pathlib import Path
import re
import struct

from scripts.overworld_application_bank_compiler import compile_bank
from scripts.overworld_behavior_profile_viewer import _runtime_source_behavior_catalog


def _constant(header: Path, name: str) -> int:
    match = re.search(r"^#define\s+" + re.escape(name) + r"\s+(\d+)\s*$",
                      header.read_text(), re.MULTILINE)
    if match is None:
        raise ValueError(f"behavior bank header lacks {name}")
    return int(match.group(1))


def decode_application_bank(blob: bytes, repo: Path) -> dict:
    """Bind species-local slots and condition owners to the packaged Blob.

    The caller must authenticate the live Blob against the package first. The
    generated C header supplies only the Arc storage count; all bank bytes are
    checked against the canonical compiler output and the complete Blob tail.
    """
    repo = Path(repo)
    header = repo / "include/overworld_wild_behavior_data.h"
    source = json.loads((repo / "data/overworld_behavior_profiles.json").read_text())
    catalog = _runtime_source_behavior_catalog(source)
    expected = compile_bank(catalog, repo / "include/constants/species.h")
    if len(blob) < 84 or struct.unpack_from("<IHHI", blob) != (0x4F574244, 95, 84, len(blob)):
        raise ValueError("behavior bank Blob header differs")
    class_count = struct.unpack_from("<H", blob, 16)[0]
    override_count = struct.unpack_from("<H", blob, 40)[0]
    condition_count = struct.unpack_from("<H", blob, 56)[0]
    template_offset, template_count, template_stride = struct.unpack_from("<IHH", blob, 76)
    if template_stride != 2 or condition_count != _constant(header, "OWBD_CONDITION_ENTRY_COUNT") \
            or override_count != _constant(header, "OWBD_OVERRIDE_PROFILE_COUNT") \
            or class_count != _constant(header, "OWBD_CLASS_PROFILE_COUNT"):
        raise ValueError("behavior bank source and Blob counts differ")
    rest = (template_offset + template_count * template_stride + 3) & ~3
    arcs = rest + 4 + max(condition_count, 1) * 18
    directory_offset = arcs + _constant(header, "OWBD_HOP_ARC_RECORD_STORAGE_COUNT") * 6
    directory_count = len(expected["rows"])
    index_count = len(expected["indexes"])
    index_offset = directory_offset + directory_count * 6
    owner_offset = index_offset + index_count * 2
    subject_offset = owner_offset + max(condition_count, 1) * 2
    keys_offset = subject_offset + max(condition_count, 1) * 2
    tint_offset = keys_offset + override_count
    tired_class_offset = tint_offset + override_count
    tired_override_offset = tired_class_offset + class_count * 2
    tail_end = tired_override_offset + override_count * 2
    if len(blob) != ((tail_end + 3) & ~3) or any(blob[tail_end:]):
        raise ValueError("behavior bank Blob tail size differs")
    rows = [struct.unpack_from("<HHBB", blob, directory_offset + 6 * i)
            for i in range(directory_count)]
    indexes = list(struct.unpack_from(f"<{index_count}H", blob, index_offset))
    if rows != [(species if isinstance(species, int) else 0xFFFF, first, count, 0)
                for species, first, count in expected["rows"]] \
            or indexes != expected["indexes"]:
        raise ValueError("behavior bank Blob bytes differ from compiler")
    if rows[-1][0] != 0xFFFF or any(a[0] >= b[0] for a, b in zip(rows[:-2], rows[1:-1])):
        raise ValueError("behavior bank directory order differs")
    owners = struct.unpack_from(f"<{condition_count}H", blob, owner_offset)
    subjects = struct.unpack_from(f"<{condition_count}H", blob, subject_offset)
    if any(value >= override_count for value in (*owners, *subjects) if value != 0xFFFF):
        raise ValueError("behavior bank condition owner exceeds catalog")
    return dict(rows=rows, indexes=indexes, conditionOwners=owners,
                conditionSubjectOwners=subjects, directoryOffset=directory_offset,
                indexOffset=index_offset, ownerOffset=owner_offset,
                applicationCount=override_count, conditionCount=condition_count)


def species_applications(bank: dict, species: int) -> tuple[int, ...]:
    row = next((row for row in bank["rows"][:-1] if row[0] == species), bank["rows"][-1])
    _, first, count, _ = row
    return tuple(bank["indexes"][first:first + count])


def global_application(bank: dict, species: int, local: int) -> int:
    applications = species_applications(bank, species)
    if not 0 <= local < len(applications):
        raise ValueError("behavior bank local application slot differs")
    return applications[local]


def local_application(bank: dict, species: int, global_id: int) -> int:
    applications = species_applications(bank, species)
    try:
        return applications.index(global_id)
    except ValueError as error:
        raise ValueError("behavior bank application is absent for subject") from error


def global_mask(bank: dict, species: int, local_mask: int) -> tuple[int, ...]:
    applications = species_applications(bank, species)
    if local_mask >> len(applications):
        raise ValueError("behavior bank local mask exceeds subject bank")
    return tuple(value for bit, value in enumerate(applications) if local_mask & (1 << bit))


def canonical_bank(repo: Path) -> dict:
    repo = Path(repo)
    source = json.loads((repo / "data/overworld_behavior_profiles.json").read_text())
    compiled = compile_bank(_runtime_source_behavior_catalog(source),
                            repo / "include/constants/species.h")
    rows = [(species if isinstance(species, int) else 0xFFFF, first, count, 0)
            for species, first, count in compiled["rows"]]
    return dict(rows=rows, indexes=compiled["indexes"])
