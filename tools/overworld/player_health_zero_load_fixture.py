"""Private, checksum-valid PH1 zero-HP cartridge fixture. Never writes the input.

USA HG layout is pinned by the stock save footer and production misc-data ABI.
Only the selected normal copy's six PH1 bytes and its footer CRC may change.
"""
import argparse
import binascii
import hashlib
import json
import struct
from pathlib import Path

SIZE = 0x80000
FOOTER = 0xFF90
MARKER = 0x28E9
HP = 0x28F1
CHECKPOINT = 0x28F2
STOCK_SPAWN = 0x1424 + 0x68
# Stock slot-0 SaveArray layout in USA HG: player-data block starts at 0x60,
# its profile money is +24, and the bag block starts at 0x644. The in-memory
# observer reads the same 2448-byte bag block including its save CRC.
MONEY = 0x60 + 24
BAG = 0x644
BAG_SIZE = 2448


def digest(data):
    return hashlib.sha256(data).hexdigest()


def selected_copy(raw):
    if len(raw) != SIZE:
        raise ValueError('expected a raw 512-KiB save')
    copies = []
    for base in (0, 0x40000):
        count, size, magic, slot, crc = struct.unpack_from('<IIIHH', raw, base + FOOTER)
        if (size, magic, slot) == (0xFFA0, 0x20060623, 0) and crc == binascii.crc_hqx(raw[base:base + FOOTER], 0xFFFF):
            copies.append((base, count))
    if not copies:
        raise ValueError('no checksum-valid normal save copy')
    if len(copies) == 1:
        return copies[0]
    delta = (copies[1][1] - copies[0][1]) & 0xFFFFFFFF
    if delta == 0x80000000:
        raise ValueError('ambiguous save counter order')
    return copies[1] if 0 < delta < 0x80000000 else copies[0]


def checkpoint_for(raw, base):
    if raw[base + MARKER:base + MARKER + 3] == b'PH\1':
        checkpoint = struct.unpack_from('<H', raw, base + CHECKPOINT)[0]
        provenance = 'existing-player-health-checkpoint'
    else:
        checkpoint = struct.unpack_from('<H', raw, base + STOCK_SPAWN)[0]
        provenance = 'legacy-stock-last-spawn'
    if not 1 <= checkpoint <= 30:
        raise ValueError('source has no valid existing checkpoint')
    return checkpoint, provenance


def verify_fixture(source, fixture):
    base, count = selected_copy(source)
    checkpoint, provenance = checkpoint_for(source, base)
    if selected_copy(fixture) != (base, count):
        raise ValueError('fixture selected copy changed')
    if fixture[base + MARKER:base + MARKER + 3] != b'PH\1':
        raise ValueError('fixture marker is not PH version 1')
    if fixture[base + HP] != 0 or struct.unpack_from('<H', fixture, base + CHECKPOINT)[0] != checkpoint:
        raise ValueError('fixture HP or checkpoint differs')
    allowed = {base + i for i in (*range(MARKER, MARKER + 3), *range(HP, HP + 3), FOOTER + 14, FOOTER + 15)}
    changed = [{'offset': i, 'before': a, 'after': b} for i, (a, b) in enumerate(zip(source, fixture)) if a != b]
    if any(row['offset'] not in allowed for row in changed):
        raise ValueError('unrelated save bytes changed')
    money = struct.unpack_from('<I', source, base + MONEY)[0]
    if money > 999999:
        raise ValueError('source money is outside the stock range')
    bag = source[base + BAG:base + BAG + BAG_SIZE]
    if len(bag) != BAG_SIZE:
        raise ValueError('source bag block is incomplete')
    if fixture[base + MONEY:base + MONEY + 4] != source[base + MONEY:base + MONEY + 4] \
            or fixture[base + BAG:base + BAG + BAG_SIZE] != bag:
        raise ValueError('fixture economy differs from source')
    unrelated = bytes(value for i, value in enumerate(source) if i not in allowed)
    return {'schemaVersion': 1, 'kind': 'player-health-zero-load-fixture',
            'acceptedProof': False, 'sourceSha256': digest(source), 'fixtureSha256': digest(fixture),
            'copyBase': base, 'saveCount': count, 'hp': 0, 'checkpointSpawn': checkpoint,
            'checkpointSource': provenance, 'allowedOffsets': sorted(allowed),
            'baselineEconomy': {'version': 1, 'money': money,
                                'bagSize': BAG_SIZE, 'bagSha256': digest(bag)},
            'changedBytes': changed, 'unchangedBytesSha256': digest(unrelated)}


def prepare_bytes(source):
    base, _ = selected_copy(source)
    checkpoint, _ = checkpoint_for(source, base)
    fixture = bytearray(source)
    fixture[base + MARKER:base + MARKER + 3] = b'PH\1'
    struct.pack_into('<BH', fixture, base + HP, 0, checkpoint)
    struct.pack_into('<H', fixture, base + FOOTER + 14,
                     binascii.crc_hqx(fixture[base:base + FOOTER], 0xFFFF))
    return bytes(fixture), verify_fixture(source, fixture)


def create_fixture(source_path, output_dir):
    source_path = Path(source_path).resolve(strict=True)
    source = source_path.read_bytes()
    fixture, manifest = prepare_bytes(source)
    # Exclusive directory creation rejects existing paths, symlinks and overwrites.
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    save_path = output_dir / 'game.sav'
    with save_path.open('xb') as stream:
        stream.write(fixture)
    if source_path.read_bytes() != source:
        raise ValueError('source save changed during fixture creation')
    manifest.update(sourcePath=str(source_path), fixturePath=str(save_path.resolve()))
    with (output_dir / 'manifest.json').open('x') as stream:
        json.dump(manifest, stream, indent=2)
        stream.write('\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('test.sav'))
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(create_fixture(args.source, args.output_dir), indent=2))


if __name__ == '__main__':
    main()
