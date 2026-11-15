#!/usr/bin/env python3
"""Check item allocation ownership and the native friendship item predicate."""
from pathlib import Path
import argparse
import hashlib
import re
import shutil
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def braced(text, start):
    opening = text.index("{", start)
    depth, end = 1, opening + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[opening:end], end


def authored_unit():
    header = (ROOT / "include/item.h").read_text()
    start = header.index("typedef struct ItemPartyUseParam")
    end = header.index("} ITEMDATA;", start) + len("} ITEMDATA;")
    macro = re.search(r"^#define ITEM_PRICE\(p\).*$", header, re.M).group()
    enum_start = header.rfind("enum", 0, header.index("ITEM_GET_DATA ="))
    _, enum_end = braced(header, enum_start)
    data = (ROOT / "data/itemdata/itemdata.c").read_text()
    initializer, _ = braced(data, data.index("[ITEM_NONE] ="))
    battle = (ROOT / "include/battle.h").read_text()
    normal = re.search(r"^#define TYPE_NORMAL\s+.*$", battle, re.M).group()
    return ("#include <stdint.h>\ntypedef uint8_t u8; typedef uint16_t u16; "
            "typedef uint32_t u32; typedef int8_t s8;\n#define FALSE 0\n"
            "#include \"constants/item.h\"\n#include \"constants/file.h\"\n"
            + normal + "\n" + header[start:end] + "\n" + macro + "\n"
            + header[enum_start:enum_end] + ";\n"
            + "const ITEMDATA authoredNone = " + initializer + ";\n")


def narc_records(data):
    if len(data) < 16 or data[:4] != b"NARC":
        raise ValueError("current item-data NARC header differs")
    bom, version, size, header, count = struct.unpack_from("<HHIHH", data, 4)
    if (bom, version, size, header, count) != (0xFFFE, 0x100, len(data), 16, 3):
        raise ValueError("current item-data NARC bounds differ")
    chunks, offset = {}, header
    for _ in range(count):
        tag, extent = struct.unpack_from("<4sI", data, offset)
        if tag in chunks or extent < 8 or extent > len(data) - offset:
            raise ValueError("current item-data chunk bounds differ")
        chunks[tag] = data[offset + 8:offset + extent]
        offset += extent
    if offset != len(data) or set(chunks) != {b"BTAF", b"BTNF", b"GMIF"}:
        raise ValueError("current item-data chunk identity differs")
    fat, image = chunks[b"BTAF"], chunks[b"GMIF"]
    if len(fat) < 12 or struct.unpack_from("<H", fat)[0] == 0:
        raise ValueError("current item-data NONE entry is absent")
    count = struct.unpack_from("<H", fat)[0]
    if len(fat) != 4 + count * 8:
        raise ValueError("current item-data record directory differs")
    records = []
    for index in range(count):
        start, end = struct.unpack_from("<II", fat, 4 + index * 8)
        if not 0 <= start <= end <= len(image):
            raise ValueError("current item-data record exceeds its image")
        records.append(image[start:end])
    return records


def narc_none(data):
    return narc_records(data)[0]


def friendship_item_rule(records):
    if not records or any(len(record) != 36 for record in records):
        raise ValueError("friendship item-data record size differs")
    if [index for index, record in enumerate(records) if record[2] == 53] != [218]:
        raise ValueError("friendship effect53 must be exactly SOOTHE_BELL218")


def authored_item_records():
    """Compile the actual complete initializer with its real item layout."""
    prefix = authored_unit().split("const ITEMDATA authoredNone =", 1)[0]
    types = "\n".join(re.findall(r"^#define TYPE_\w+\s+[^\n]+",
                                (ROOT / "include/battle.h").read_text(), re.M))
    table = (ROOT / "data/itemdata/itemdata.c").read_text().split(
        "const ITEMDATA __data[] =", 1)[1]
    program = ("#include <stdio.h>\n#include <stddef.h>\n#define TRUE 1\n" + prefix
        + "\n" + types + '\n#include "constants/hold_item_effects.h"\n'
        + "const ITEMDATA __data[] =" + table + "\n"
        + '_Static_assert(sizeof(ITEMDATA)==36,"item ABI");\n'
        + '_Static_assert(offsetof(ITEMDATA,holdEffect)==2,"hold effect ABI");\n'
        + '_Static_assert(ITEM_SOOTHE_BELL==218,"native friendship item immediate");\n'
        + '_Static_assert(HOLD_EFFECT_FRIENDSHIP_UP==53,"native friendship effect");\n'
        + "int main(void){return fwrite(__data,sizeof(__data),1,stdout)!=1;}\n")
    with tempfile.TemporaryDirectory(prefix="friendship-item-data-") as temporary:
        directory = Path(temporary)
        path, executable = directory / "items.c", directory / "items"
        path.write_text(program)
        subprocess.run([shutil.which("cc") or "cc", "-std=c11", "-O2", "-Wall",
            "-Wextra", "-Werror", "-I", str(ROOT / "include"), str(path), "-o",
            str(executable)], check=True, capture_output=True)
        data = subprocess.run([str(executable)], check=True, capture_output=True).stdout
    if len(data) % 36:
        raise ValueError("authored item array size differs")
    return [data[offset:offset + 36] for offset in range(0, len(data), 36)]


DRIVER = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"no-item line%d: %s\n",__LINE__,#x); return 1; } } while(0)
static u32 allocHeap,allocSize,archiveId,archiveMember,archiveHeap;
static unsigned allocations,archiveCalls; static int failAlloc;
static u8 archiveMarker;
void *sys_AllocMemory(u32 heap,u32 size) {
    ++allocations; allocHeap=heap; allocSize=size;
    if (failAlloc) return NULL;
    void *p=malloc(size); if(p) memset(p,0xA5,size); return p;
}
static void *ArchiveDataLoadMalloc(u32 archive,u32 member,u32 heap) {
    ++archiveCalls; archiveId=archive; archiveMember=member; archiveHeap=heap;
    return &archiveMarker;
}
'''

CHECKS = r'''
int main(int argc,char **argv) {
    CHECK(sizeof(ITEMDATA)==36 && TYPE_NORMAL==0 && POCKET_ITEMS==0 && BATTLE_POCKET_NONE==0);
    const u8 *original=(const u8 *)&authoredNone;
    for(unsigned i=0;i<sizeof(authoredNone);i++) CHECK(original[i]==0);
    if(argc==2) { FILE *f=fopen(argv[1],"wb");CHECK(f);CHECK(fwrite(original,1,sizeof(authoredNone),f)==sizeof(authoredNone));CHECK(!fclose(f)); }
    void *first=GetItemArcData(ITEM_NONE,ITEM_GET_DATA,4);
    CHECK(archiveCalls==0 && allocations==1 && allocHeap==4 && allocSize==sizeof(ITEMDATA));
    CHECK(first && !memcmp(first,&authoredNone,sizeof(ITEMDATA)));
    ((u8 *)first)[0]=0xCC;
    void *second=GetItemArcData(ITEM_NONE,ITEM_GET_DATA,11);
    CHECK(second && second!=first && archiveCalls==0 && allocations==2 && allocHeap==11);
    CHECK(!memcmp(second,&authoredNone,sizeof(ITEMDATA)) && ((u8 *)first)[0]==0xCC);
    free(first);free(second);failAlloc=1;
    CHECK(GetItemArcData(ITEM_NONE,ITEM_GET_DATA,3)==NULL);
    CHECK(allocations==3 && allocHeap==3 && allocSize==sizeof(ITEMDATA) && archiveCalls==0);
    for(unsigned i=1;i<=MAX_TOTAL_ITEM_NUM;i++) {
        CHECK(GetItemArcData(i,ITEM_GET_DATA,7)==&archiveMarker);
        CHECK(archiveId==ARC_ITEM_DATA && archiveMember==i && archiveHeap==7);
    }
    CHECK(allocations==3 && archiveCalls==MAX_TOTAL_ITEM_NUM);
    for(unsigned i=0;i<=MAX_TOTAL_ITEM_NUM;i++) {
        CHECK(GetItemArcData(i,ITEM_GET_ICON_CGX,9)==&archiveMarker);
        CHECK(archiveId==ARC_ITEM_GFX_DATA && archiveMember==i*2+2 && archiveHeap==9);
        CHECK(GetItemArcData(i,ITEM_GET_ICON_PAL,9)==&archiveMarker);
        CHECK(archiveId==ARC_ITEM_GFX_DATA && archiveMember==i*2+3 && archiveHeap==9);
    }
    unsigned before=archiveCalls;
    CHECK(GetItemArcData(ITEM_NONE,ITEM_GET_AGB_NUM,5)==NULL);
    CHECK(GetItemArcData(ITEM_NONE,0xFFFF,5)==NULL && archiveCalls==before && allocations==3);
    puts("PASS real zero NONE bytes; fresh caller heap/size/ownership/failure; every other item/icon/palette unchanged");
    return 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "src/item.c")
    args = parser.parse_args()
    authored = authored_item_records()
    friendship_item_rule(authored)
    for name in ("build/narc/itemdata.narc", "base/root/a/0/1/7"):
        built = narc_records((ROOT / name).read_bytes())
        friendship_item_rule(built)
        if built != authored:
            raise SystemExit("authored/current full item array differs: " + name)
    # Either another friendship item or a changed Soothe Bell must stop this
    # native predicate before packaging. Include a >255 low-byte alias too.
    for item, effect in ((193, 53), (474, 53), (218, 0)):
        changed = list(authored)
        record = bytearray(changed[item])
        record[2] = effect
        changed[item] = bytes(record)
        try:
            friendship_item_rule(changed)
        except ValueError:
            pass
        else:
            raise SystemExit("changed friendship item rule passed admission")
    print("PASS full authored/current item equality; friendship effect53 only218; future item changes rejected")
    source = args.source.read_text()
    start = source.index("void *GetItemArcData(u16 item, u16 type, u32 heap_id)\n{")
    _, end = braced(source, start)
    helper = ""
    marker = "Item_LoadData(u32 archive, u32 member, u32 heap_id)"
    if marker in source:
        helper_start = source.index(marker)
        _, helper_end = braced(source, helper_start)
        # Only native placement/calling attributes are omitted. This executes
        # the unchanged actual helper and public dispatcher bodies together.
        helper = "static void *" + source[helper_start:helper_end] + "\n"
    unit = authored_unit() + DRIVER + helper + source[start:end] + CHECKS
    with tempfile.TemporaryDirectory(prefix="no-item-data-") as temporary:
        directory = Path(temporary)
        path, executable, native = directory / "check.c", directory / "check", directory / "authored.bin"
        path.write_text(unit)
        command = [shutil.which("cc") or "cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(ROOT / "include")]
        subprocess.run(command + [str(path), "-o", str(executable)], check=True)
        subprocess.run([str(executable), str(native)], check=True)
        for name in ("build/narc/itemdata.narc", "base/root/a/0/1/7"):
            if narc_none((ROOT / name).read_bytes()) != native.read_bytes():
                raise SystemExit("authored/current built NONE bytes differ: " + name)
        # A future nonzero NONE field must stop the proof before this shortcut.
        marker = "const ITEMDATA authoredNone = {"
        if unit.count(marker) != 1:
            raise SystemExit("NONE initializer extraction changed")
        changed = unit.replace(marker, marker + "\n.holdEffect=1,", 1)
        # Replace the existing field rather than a duplicate initializer.
        changed = changed.replace(".holdEffect = 0,", "", 1)
        path.write_text(changed)
        subprocess.run(command + [str(path), "-o", str(executable)], check=True)
        result = subprocess.run([str(executable)], capture_output=True, text=True)
        if result.returncode == 0 or "original[i]==0" not in result.stderr:
            raise SystemExit("future nonzero NONE data did not stop admission")
        print("PASS authored/current NARC NONE equality; nonzero authored-data mutant rejected")
    for name in (args.source, ROOT / "data/itemdata/itemdata.c", ROOT / "include/item.h", Path(__file__)):
        print(name, hashlib.sha256(name.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
