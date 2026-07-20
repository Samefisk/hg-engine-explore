#!/usr/bin/env python3
"""Build and exhaustively validate the overworld-wild spawn metadata cache."""

from __future__ import annotations

import argparse
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path


OWSM_MAGIC = 0x4F57534D
OWSM_VERSION = 2
OWSM_HEADER_SIZE = 36
OWSM_RECORD_SIZE = 8
OWSM_EXCEPTION_SIZE = 12
OWSM_CHECKSUM_OFFSET = 32
OWSM_MAX_ENCODED_FORM = 31
OWSM_EXPECTED_DENSE_RECORD_COUNT = 1076
NEEDS_REVERSION = 0x8000
OVERLAY_1_RENDER_DESCRIPTOR_OFFSET = 0x21A18
OVERLAY_1_RENDER_DESCRIPTOR_SIZE = 8
OVERLAY_1_RENDER_MODE_OFFSET = 2

SPECIES_PIKACHU = 25
SPECIES_SLOWBRO = 80
SPECIES_HOOTHOOT = 163
SPECIES_DEOXYS = 386
SPECIES_WORMADAM = 413
SPECIES_ROTOM = 479
SPECIES_GIRATINA = 487
SPECIES_SHAYMIN = 492
SPECIES_FINNEON = 456


def parse_object_define(source: str, name: str) -> int:
    match = re.search(
        rf"^\s*#define\s+{re.escape(name)}\s+([^\s/]+)",
        source,
        re.MULTILINE,
    )
    require(match is not None, f"format header is missing {name}")
    value = match.group(1).rstrip("uUlL")
    try:
        return int(value, 0)
    except ValueError as exc:
        raise ValueError(f"format header has non-integer {name}: {value}") from exc


def parse_struct_layout(
    source: str,
    name: str,
    known_types: dict[str, tuple[int, int]],
) -> tuple[int, int, dict[str, int]]:
    match = re.search(
        rf"typedef\s+struct\s+{re.escape(name)}\s*\{{(.*?)\}}\s*{re.escape(name)}\s*;",
        source,
        re.DOTALL,
    )
    require(match is not None, f"format header is missing struct {name}")
    offset = 0
    struct_alignment = 1
    offsets: dict[str, int] = {}
    declarations = [
        line.strip()
        for line in match.group(1).splitlines()
        if line.strip()
    ]
    for declaration in declarations:
        field = re.fullmatch(r"([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*;", declaration)
        require(field is not None, f"unsupported {name} field declaration: {declaration}")
        field_type, field_name = field.groups()
        require(field_type in known_types, f"unsupported {name} field type: {field_type}")
        field_size, field_alignment = known_types[field_type]
        offset = (offset + field_alignment - 1) & ~(field_alignment - 1)
        offsets[field_name] = offset
        offset += field_size
        struct_alignment = max(struct_alignment, field_alignment)
    size = (offset + struct_alignment - 1) & ~(struct_alignment - 1)
    return size, struct_alignment, offsets


def validate_shared_format_header(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    constants = {
        "OVERWORLD_WILD_SPAWN_METADATA_MAGIC": OWSM_MAGIC,
        "OVERWORLD_WILD_SPAWN_METADATA_VERSION": OWSM_VERSION,
        "OVERWORLD_WILD_SPAWN_METADATA_MAX_FORM": OWSM_MAX_ENCODED_FORM,
    }
    for name, expected in constants.items():
        actual = parse_object_define(source, name)
        require(actual == expected, f"{path}: {name} is {actual}, expected {expected}")

    known_types = {"u8": (1, 1), "u16": (2, 2), "u32": (4, 4)}
    record_size, record_alignment, _ = parse_struct_layout(
        source, "OverworldWildSpawnMetadata", known_types
    )
    known_types["OverworldWildSpawnMetadata"] = (record_size, record_alignment)
    exception_size, _, _ = parse_struct_layout(
        source, "OverworldWildSpawnMetadataException", known_types
    )
    header_size, _, header_offsets = parse_struct_layout(
        source, "OverworldWildSpawnMetadataBlobHeader", known_types
    )
    require(record_size == OWSM_RECORD_SIZE, f"{path}: metadata record size is {record_size}, expected {OWSM_RECORD_SIZE}")
    require(exception_size == OWSM_EXCEPTION_SIZE, f"{path}: exception record size is {exception_size}, expected {OWSM_EXCEPTION_SIZE}")
    require(header_size == OWSM_HEADER_SIZE, f"{path}: blob header size is {header_size}, expected {OWSM_HEADER_SIZE}")
    require(
        header_offsets.get("checksum") == OWSM_CHECKSUM_OFFSET,
        f"{path}: checksum offset is {header_offsets.get('checksum')}, expected {OWSM_CHECKSUM_OFFSET}",
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_elf_section(path: Path, section_name: bytes) -> bytes:
    blob = path.read_bytes()
    require(len(blob) >= 52, f"{path}: truncated ELF header")
    require(blob[:6] == b"\x7fELF\x01\x01", f"{path}: expected little-endian ELF32")
    section_offset = struct.unpack_from("<I", blob, 0x20)[0]
    section_entry_size, section_count, names_index = struct.unpack_from("<HHH", blob, 0x2E)
    require(section_entry_size >= 40, f"{path}: invalid ELF section-entry size")
    require(names_index < section_count, f"{path}: invalid ELF section-name table index")
    require(
        section_offset + section_entry_size * section_count <= len(blob),
        f"{path}: truncated ELF section table",
    )

    def section_header(index: int) -> tuple[int, int, int]:
        offset = section_offset + index * section_entry_size
        name_offset = struct.unpack_from("<I", blob, offset)[0]
        data_offset, data_size = struct.unpack_from("<II", blob, offset + 0x10)
        require(data_offset + data_size <= len(blob), f"{path}: section {index} is out of bounds")
        return name_offset, data_offset, data_size

    _, names_offset, names_size = section_header(names_index)
    names = blob[names_offset : names_offset + names_size]
    for index in range(section_count):
        name_offset, data_offset, data_size = section_header(index)
        require(name_offset < len(names), f"{path}: section {index} has an invalid name")
        name_end = names.find(b"\0", name_offset)
        require(name_end >= 0, f"{path}: section {index} name is unterminated")
        if names[name_offset:name_end] == section_name:
            return blob[data_offset : data_offset + data_size]
    raise ValueError(f"{path}: missing ELF section {section_name.decode()}")


def read_narc_members(path: Path) -> list[bytes]:
    blob = path.read_bytes()
    require(len(blob) >= 16, f"{path}: truncated NARC header")
    magic, byte_order, version, file_size, header_size, chunk_count = struct.unpack_from(
        "<4sHHIHH", blob, 0
    )
    require(magic == b"NARC", f"{path}: bad NARC magic")
    require(byte_order == 0xFFFE, f"{path}: unsupported byte order")
    require(version == 0x0100, f"{path}: unsupported NARC version")
    require(file_size == len(blob), f"{path}: NARC file-size mismatch")
    require(header_size == 16, f"{path}: unexpected NARC header size")
    require(chunk_count == 3, f"{path}: expected exactly three NARC chunks")

    chunks: list[tuple[bytes, int, int]] = []
    chunk_offset = header_size
    for chunk_index in range(chunk_count):
        require(chunk_offset + 8 <= len(blob), f"{path}: truncated chunk {chunk_index} header")
        signature, chunk_size = struct.unpack_from("<4sI", blob, chunk_offset)
        require(chunk_size >= 8, f"{path}: invalid chunk {chunk_index} size")
        require(chunk_offset + chunk_size <= len(blob), f"{path}: truncated chunk {chunk_index}")
        chunks.append((signature, chunk_offset, chunk_size))
        chunk_offset += chunk_size
    require(chunk_offset == len(blob), f"{path}: trailing bytes after final NARC chunk")
    require(
        [chunk[0] for chunk in chunks] == [b"BTAF", b"BTNF", b"GMIF"],
        f"{path}: NARC chunks are missing or out of order",
    )

    _, fat_offset, fat_size = chunks[0]
    require(fat_size >= 12, f"{path}: truncated BTAF chunk")
    member_count, fat_reserved = struct.unpack_from("<HH", blob, fat_offset + 8)
    require(fat_reserved == 0, f"{path}: nonzero BTAF reserved field")
    require(fat_size == 12 + member_count * 8, f"{path}: BTAF size does not match member count")
    entries_offset = fat_offset + 12
    _, data_offset, data_size = chunks[2]
    data_start = data_offset + 8
    data_payload_size = data_size - 8
    members: list[bytes] = []
    previous_end = 0
    for member_index in range(member_count):
        start, end = struct.unpack_from("<II", blob, entries_offset + member_index * 8)
        require(
            previous_end <= start <= end <= data_payload_size,
            f"{path}: invalid or overlapping member {member_index} range",
        )
        members.append(blob[data_start + start:data_start + end])
        previous_end = end
    return members


@dataclass(frozen=True)
class SpawnMetadata:
    sprite_id: int
    follower_param: int
    type1: int
    type2: int
    catch_value: int
    render_mode_plus_one: int

    def encode(self) -> bytes:
        return struct.pack(
            "<HHBBBB",
            self.sprite_id,
            self.follower_param,
            self.type1,
            self.type2,
            self.catch_value,
            self.render_mode_plus_one,
        )


class MetadataSources:
    def __init__(
        self,
        personal_members: list[bytes],
        overworld_members: list[bytes],
        form_counts: bytes,
        base_models: bytes,
        form_species: bytes,
        render_table: bytes,
        render_descriptors: bytes,
    ) -> None:
        require(len(form_counts) != 0, "form-count table is empty")
        require(len(base_models) == len(form_counts) * 2, "base-model table length differs from form-count table")
        require(len(form_species) % 64 == 0, "form-species table is not made of 32-u16 rows")
        self.personal_members = personal_members
        self.overworld_members = overworld_members
        self.form_counts = form_counts
        self.base_models = struct.unpack(f"<{len(base_models) // 2}H", base_models)
        self.form_species = form_species
        require(len(render_table) != 0 and len(render_table) % 6 == 0, "render table is not made of 6-byte rows")
        self.render_modes: dict[int, int] = {}
        for offset in range(0, len(render_table), 6):
            tag, _gfx, callback_params = struct.unpack_from("<HHH", render_table, offset)
            descriptor = (callback_params >> 10) & 0x3F
            mode_offset = (
                OVERLAY_1_RENDER_DESCRIPTOR_OFFSET
                + descriptor * OVERLAY_1_RENDER_DESCRIPTOR_SIZE
                + OVERLAY_1_RENDER_MODE_OFFSET
            )
            require(
                mode_offset < len(render_descriptors),
                f"render descriptor {descriptor} is outside built overlay 1",
            )
            mode_plus_one = render_descriptors[mode_offset] + 1
            require(1 <= mode_plus_one <= 64, f"render descriptor {descriptor} has invalid mode")
            self.render_modes.setdefault(tag, mode_plus_one)
        self.base_count = len(form_counts)
        self.form_species_base_count = len(form_species) // 64
        require(
            self.base_count == OWSM_EXPECTED_DENSE_RECORD_COUNT,
            f"expected {OWSM_EXPECTED_DENSE_RECORD_COUNT} dense records, got {self.base_count}",
        )

    def adjusted_personal_species(self, species: int, form: int) -> int:
        if species == SPECIES_DEOXYS:
            return 495 + form if 0 < form <= 3 else species
        if species == SPECIES_WORMADAM:
            return 498 + form if 0 < form <= 2 else species
        if species == SPECIES_GIRATINA:
            return 500 + form if 0 < form <= 1 else species
        if species == SPECIES_SHAYMIN:
            return 501 + form if 0 < form <= 1 else species
        if species == SPECIES_ROTOM:
            return 502 + form if 0 < form <= 5 else species
        if form != 0:
            offset = (species * 32 + form - 1) * 2
            require(offset + 2 <= len(self.form_species), f"form table lacks species {species}, form {form}")
            adjusted = struct.unpack_from("<H", self.form_species, offset)[0] & ~NEEDS_REVERSION
            if adjusted != 0:
                return adjusted
        return species

    def model_index(self, species: int, form: int) -> int:
        model = self.base_models[species]
        if self.form_counts[species] != 0 and form <= self.form_counts[species]:
            model += form
        return model

    def sprite_id(self, species: int, form: int) -> int:
        sprite_id = self.base_models[species]
        sprite_id += 0x1E4 if species > SPECIES_FINNEON else 0x1AC
        max_form = self.form_counts[species]
        if species == SPECIES_PIKACHU:
            if form != 0:
                sprite_id += 1
            if form < max_form:
                sprite_id += form
        elif species == SPECIES_SLOWBRO and form != 0:
            new_form = form - 1
            if new_form <= max_form:
                sprite_id += new_form
        elif form <= max_form:
            sprite_id += form
        return sprite_id

    def metadata(self, species: int, form: int) -> SpawnMetadata:
        require(0 <= species < self.base_count, f"species {species} is outside dense table")
        require(0 <= form <= OWSM_MAX_ENCODED_FORM, f"form {form} is not encodable by overworld wild state")
        personal_species = self.adjusted_personal_species(species, form)
        require(personal_species < len(self.personal_members), f"personal member {personal_species} is unavailable")
        personal = self.personal_members[personal_species]
        require(len(personal) >= 9, f"personal member {personal_species} is truncated")
        model_index = self.model_index(species, form)
        require(model_index < len(self.overworld_members), f"overworld member {model_index} is unavailable")
        overworld = self.overworld_members[model_index]
        require(len(overworld) >= 3, f"overworld member {model_index} is truncated")
        catch_rate = personal[8]
        sprite_id = self.sprite_id(species, form)
        require(sprite_id in self.render_modes, f"render table lacks emitted sprite tag {sprite_id}")
        return SpawnMetadata(
            sprite_id=sprite_id,
            follower_param=(overworld[1] << 8) | overworld[2],
            type1=personal[6],
            type2=personal[7],
            catch_value=(catch_rate + 2) // 3,
            render_mode_plus_one=self.render_modes[sprite_id],
        )


def checksum(blob: bytes) -> int:
    scratch = bytearray(blob)
    struct.pack_into("<I", scratch, OWSM_CHECKSUM_OFFSET, 0)
    return sum(scratch) & 0xFFFFFFFF


def build_blob(sources: MetadataSources) -> bytes:
    base_records = [sources.metadata(species, 0) for species in range(sources.base_count)]
    exceptions: list[tuple[int, int, SpawnMetadata]] = []
    for species, base_record in enumerate(base_records):
        if species >= sources.form_species_base_count:
            continue
        for form in range(1, OWSM_MAX_ENCODED_FORM + 1):
            record = sources.metadata(species, form)
            if record != base_record:
                exceptions.append((species, form, record))

    base_offset = OWSM_HEADER_SIZE
    exceptions_offset = base_offset + len(base_records) * OWSM_RECORD_SIZE
    total_size = exceptions_offset + len(exceptions) * OWSM_EXCEPTION_SIZE
    header = struct.pack(
        "<IHHIIHHIHHHHI",
        OWSM_MAGIC,
        OWSM_VERSION,
        OWSM_HEADER_SIZE,
        total_size,
        base_offset,
        len(base_records),
        OWSM_RECORD_SIZE,
        exceptions_offset,
        len(exceptions),
        OWSM_EXCEPTION_SIZE,
        sources.form_species_base_count,
        0,
        0,
    )
    payload = bytearray(header)
    for record in base_records:
        payload.extend(record.encode())
    for species, form, record in exceptions:
        payload.extend(struct.pack("<HBB", species, form, 0))
        payload.extend(record.encode())
    require(len(payload) == total_size, "internal blob size mismatch")
    struct.pack_into("<I", payload, OWSM_CHECKSUM_OFFSET, checksum(payload))
    return bytes(payload)


def decode_record(blob: bytes, offset: int) -> SpawnMetadata:
    sprite_id, follower_param, type1, type2, catch_value, render_mode_plus_one = struct.unpack_from(
        "<HHBBBB", blob, offset
    )
    require(1 <= render_mode_plus_one <= 64, f"record at {offset} has invalid render mode")
    return SpawnMetadata(sprite_id, follower_param, type1, type2, catch_value, render_mode_plus_one)


def validate_blob(blob: bytes, sources: MetadataSources, label: str) -> tuple[int, int]:
    require(len(blob) >= OWSM_HEADER_SIZE, f"{label}: truncated header")
    fields = struct.unpack_from("<IHHIIHHIHHHHI", blob, 0)
    (
        magic,
        version,
        header_size,
        total_size,
        base_offset,
        base_count,
        base_record_size,
        exceptions_offset,
        exception_count,
        exception_record_size,
        form_species_base_count,
        flags,
        stored_checksum,
    ) = fields
    require(magic == OWSM_MAGIC, f"{label}: bad magic")
    require(version == OWSM_VERSION, f"{label}: bad version")
    require(header_size == OWSM_HEADER_SIZE, f"{label}: bad header size")
    require(total_size == len(blob), f"{label}: total size mismatch")
    require(base_offset == header_size, f"{label}: dense records do not immediately follow header")
    require(base_count == sources.base_count, f"{label}: dense record count mismatch")
    require(base_record_size == OWSM_RECORD_SIZE, f"{label}: bad dense record size")
    require(exceptions_offset == base_offset + base_count * base_record_size, f"{label}: bad exception offset")
    require(exception_record_size == OWSM_EXCEPTION_SIZE, f"{label}: bad exception record size")
    require(form_species_base_count == sources.form_species_base_count, f"{label}: form-table coverage mismatch")
    require(form_species_base_count <= base_count, f"{label}: form-table coverage exceeds dense table")
    require(flags == 0, f"{label}: bad flags")
    require(total_size == exceptions_offset + exception_count * exception_record_size, f"{label}: bad exception range")
    require(stored_checksum == checksum(blob), f"{label}: bad checksum")

    decoded_base = [decode_record(blob, base_offset + species * base_record_size) for species in range(base_count)]
    exception_records: dict[tuple[int, int], SpawnMetadata] = {}
    previous_key: tuple[int, int] | None = None
    for index in range(exception_count):
        offset = exceptions_offset + index * exception_record_size
        species, form, reserved = struct.unpack_from("<HBB", blob, offset)
        require(reserved == 0, f"{label}: exception {index} has nonzero reserved byte")
        key = (species, form)
        require(species < base_count and 0 < form <= OWSM_MAX_ENCODED_FORM, f"{label}: invalid exception key {key}")
        require(previous_key is None or previous_key < key, f"{label}: exceptions are not sorted and unique")
        previous_key = key
        exception_records[key] = decode_record(blob, offset + 4)

    expected_exception_count = 0
    for species in range(base_count):
        expected_base = sources.metadata(species, 0)
        require(decoded_base[species] == expected_base, f"{label}: dense species {species} differs from built data")
        if species >= form_species_base_count:
            continue
        for form in range(1, OWSM_MAX_ENCODED_FORM + 1):
            expected = sources.metadata(species, form)
            actual = exception_records.get((species, form), decoded_base[species])
            require(actual == expected, f"{label}: species {species}, form {form} differs from built data")
            if expected != expected_base:
                expected_exception_count += 1
                require((species, form) in exception_records, f"{label}: missing exception {(species, form)}")
            else:
                require((species, form) not in exception_records, f"{label}: redundant exception {(species, form)}")
    require(exception_count == expected_exception_count, f"{label}: exception count mismatch")

    hoothoot = sources.metadata(SPECIES_HOOTHOOT, 0)
    hoothoot_personal = sources.personal_members[SPECIES_HOOTHOOT]
    require(hoothoot_personal[8] == 255, "Hoothoot fixture catch rate is not 255")
    require(
        hoothoot == SpawnMetadata(646, 0, 0, 2, 85, 1),
        f"Hoothoot fixture mismatch: {hoothoot}",
    )
    return base_count, exception_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mondata-narc", type=Path, required=True)
    parser.add_argument("--overworld-properties-narc", type=Path, required=True)
    parser.add_argument("--form-counts", type=Path, required=True)
    parser.add_argument("--base-models", type=Path, required=True)
    parser.add_argument("--form-species", type=Path, required=True)
    parser.add_argument("--render-table", type=Path, required=True)
    parser.add_argument("--render-descriptors", type=Path, required=True)
    parser.add_argument(
        "--format-header",
        type=Path,
        default=Path("include/overworld_wild_behavior_data.h"),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    require(args.output is not None or args.verify is not None, "provide --output or --verify")

    try:
        validate_shared_format_header(args.format_header)
        sources = MetadataSources(
            read_narc_members(args.mondata_narc),
            read_narc_members(args.overworld_properties_narc),
            args.form_counts.read_bytes(),
            args.base_models.read_bytes(),
            args.form_species.read_bytes(),
            read_elf_section(args.render_table, b".data"),
            args.render_descriptors.read_bytes(),
        )
        if args.output is not None:
            blob = build_blob(sources)
            base_count, exception_count = validate_blob(blob, sources, str(args.output))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(blob)
            print(f"wrote OWSM v{OWSM_VERSION}: {base_count} dense records, {exception_count} form exceptions, {len(blob)} bytes")
        if args.verify is not None:
            base_count, exception_count = validate_blob(args.verify.read_bytes(), sources, str(args.verify))
            print(f"verified OWSM v{OWSM_VERSION}: {base_count} dense records, {exception_count} form exceptions")
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
