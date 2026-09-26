"""Actual-C metadata load/decode/cleanup capacity tests; no ROM execution.

Uses the current generated blob, not a fixed historical byte count. Native
archive and heap calls are stubs. Exact-cap admission is separate from format
validity: the current record layout cannot necessarily encode that byte size.
"""
import importlib.util
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import unittest

from scripts import build_overworld_wild_spawn_metadata as generator

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c"
SPAWNS_SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
BLOB = ROOT / "build/OverworldWildSpawnMetadata.bin"


def harness(cap_override=None):
    spec = importlib.util.spec_from_file_location("metadata_capacity_extract",
        ROOT / "scripts/verify_overworld_spawn_profile_lifecycle.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    source = SOURCE.read_text()
    header = (ROOT / "include/overworld_wild_behavior_data.h").read_text()
    cap = re.search(r"size\s*<=\s*(\w+MAX_BLOB_SIZE)", source)
    if cap is None:
        raise ValueError("actual loader capacity guard missing")
    constants = []
    for name in (cap[1], "OVERWORLD_WILD_SPAWN_METADATA_MAGIC",
                 "OVERWORLD_WILD_SPAWN_METADATA_VERSION", "OVERWORLD_WILD_SPAWN_METADATA_MAX_FORM"):
        definitions = re.findall(r"^#define\s+" + name + r"\s+([^\n]+)", header + "\n" + source, re.M)
        if len(definitions) != 1:
            raise ValueError("expected one capacity/format constant: " + name)
        value = str(cap_override) if name == cap[1] and cap_override is not None else definitions[0]
        constants.append("#define " + name + " " + value)
    structs = []
    for name in ("OverworldWildSpawnMetadata", "OverworldWildSpawnMetadataException",
                 "OverworldWildSpawnMetadataBlobHeader"):
        match = re.search(r"typedef struct " + name + r"\s*\{[^}]*\}\s*" + name + r";", header)
        if match is None:
            raise ValueError("missing actual format struct " + name)
        structs.append(match[0])
    body = "\n".join(helper.production_function(source, "OverworldWildBehavior_" + name, result)
        for name,result in (("SpawnMetadataChecksum","u32"),("DecodeSpawnMetadata","BOOL"),
                            ("CleanupSpawnMetadata","void")))
    # A separate stub mode tests the loader's exact inclusive byte boundary.
    load = helper.production_function(source,"OverworldWildBehavior_LoadSpawnMetadata","BOOL")
    load = load.replace("OverworldWildBehavior_DecodeSpawnMetadata()", "decode_checked()")
    lookup = helper.production_function(source,"OverworldWildBehavior_TryGetSpawnMetadata","BOOL")
    return PRELUDE + "\n".join(constants + structs) + "\n#define TEST_CAP " + cap[1] + "\n" + STUBS + body + r'''
static BOOL decode_checked(void) {
    decodes++;
    return boundary_only ? TRUE : OverworldWildBehavior_DecodeSpawnMetadata();
}
''' + load + lookup + DRIVER


PRELUDE = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "constants/species.h"
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define HEAPID_DEFAULT 0
#define HEAPID_MAIN_HEAP 3
#define HEAPID_WORLD 4
#define OVERWORLD_WILD_SPAWN_METADATA_HEAP_ID HEAPID_DEFAULT
#define ARC_CODE_ADDONS 1
#define CODE_ADDON_OVERWORLD_WILD_SPAWN_METADATA 3
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x); return 1; } } while (0)
'''

STUBS = r'''
static void *sOverworldWildSpawnMetadataBlob;
static u32 sOverworldWildSpawnMetadataBlobSize;
static BOOL sOverworldWildSpawnMetadataLoadAttempted;
static u8 *input;
static u32 input_size;
static unsigned opens, closes, allocs, frees, reads, decodes;
static BOOL boundary_only, fail_open, fail_alloc, missing_member;
static void *owned;
static void *NARC_ctor(int arc,int heap) {
    if(arc!=ARC_CODE_ADDONS||heap!=HEAPID_WORLD)abort();
    opens++;return fail_open?NULL:&opens;
}
static void NARC_dtor(void *narc) {if(narc!=&opens)abort();closes++;}
static unsigned NARC_GetFileCount(void *narc) {
    if(narc!=&opens)abort();return CODE_ADDON_OVERWORLD_WILD_SPAWN_METADATA+(missing_member?0:1);
}
static u32 NARC_GetMemberSize(void *narc,int member) {
    if(narc!=&opens||member!=CODE_ADDON_OVERWORLD_WILD_SPAWN_METADATA)abort();return input_size;
}
static void *sys_AllocMemory(int heap,u32 size) {
    if(heap!=OVERWORLD_WILD_SPAWN_METADATA_HEAP_ID||size!=input_size||owned)abort();allocs++;
    return owned=fail_alloc?NULL:malloc(size);
}
static void sys_FreeMemoryEz(void *value) {
    if(!value||value!=owned)abort();frees++;free(value);owned=NULL;
}
static void NARC_ReadWholeMember(void *narc,int member,void *out) {
    if(narc!=&opens||member!=CODE_ADDON_OVERWORLD_WILD_SPAWN_METADATA||out!=owned)abort();
    reads++;memcpy(out,input,input_size);
}
'''

DRIVER = r'''
static void reset(void) {
    OverworldWildBehavior_CleanupSpawnMetadata();
    opens=closes=allocs=frees=reads=decodes=0;
    boundary_only=fail_open=fail_alloc=missing_member=FALSE;
}
static int terminal(unsigned expected_frees) {
    CHECK(sOverworldWildSpawnMetadataLoadAttempted);
    CHECK(!sOverworldWildSpawnMetadataBlob&&!sOverworldWildSpawnMetadataBlobSize);
    CHECK(frees==expected_frees);
    unsigned old_opens=opens,old_allocs=allocs,old_decodes=decodes;
    CHECK(!OverworldWildBehavior_LoadSpawnMetadata());
    CHECK(opens==old_opens&&allocs==old_allocs&&decodes==old_decodes);
    OverworldWildBehavior_CleanupSpawnMetadata();
    CHECK(!sOverworldWildSpawnMetadataLoadAttempted&&frees==expected_frees);
    return 0;
}
int main(int argc,char **argv) {
    CHECK(argc==3);
    FILE *file=fopen(argv[1],"rb");CHECK(file);
    CHECK(fseek(file,0,SEEK_END)==0);long size=ftell(file);CHECK(size>0&&size<1048576);
    rewind(file);input=calloc((size_t)size+TEST_CAP+1,1);CHECK(input);
    CHECK(fread(input,1,(size_t)size,file)==(size_t)size);fclose(file);input_size=(u32)size;
    OverworldWildSpawnMetadataBlobHeader *header=(void*)input;
    CHECK(header->totalSize==input_size&&header->headerSize==sizeof(*header));
    if(!strcmp(argv[2],"generated")) {
        CHECK(OverworldWildBehavior_LoadSpawnMetadata());
        CHECK(input_size<=TEST_CAP&&allocs==1&&reads==1&&decodes==1&&opens==1&&closes==1);
        CHECK(OverworldWildBehavior_LoadSpawnMetadata()&&allocs==1&&decodes==1);
        OverworldWildSpawnMetadata result;
        const OverworldWildSpawnMetadata *base=(void*)(input+header->baseOffset);
        CHECK(OverworldWildBehavior_TryGetSpawnMetadata(72,0,&result));
        CHECK(!memcmp(&result,&base[72],sizeof(result)));
        CHECK(OverworldWildBehavior_TryGetSpawnMetadata(163,0,&result));
        CHECK(!memcmp(&result,&base[163],sizeof(result)));
        OverworldWildBehavior_CleanupSpawnMetadata();
        CHECK(frees==1&&!owned&&!sOverworldWildSpawnMetadataLoadAttempted);
        OverworldWildBehavior_CleanupSpawnMetadata();CHECK(frees==1);
    } else if(!strcmp(argv[2],"generated-too-large")) {
        CHECK(input_size>TEST_CAP);
        CHECK(!OverworldWildBehavior_LoadSpawnMetadata());
        CHECK(!allocs&&!reads&&!decodes&&opens==1&&closes==1);CHECK(!terminal(0));
    } else if(!strcmp(argv[2],"boundaries")) {
        // Encode the largest structurally valid record table below the cap.
        CHECK(header->exceptionsOffset<=TEST_CAP);
        header->exceptionCount=(TEST_CAP-header->exceptionsOffset)/sizeof(OverworldWildSpawnMetadataException);
        CHECK(header->exceptionCount<(MAX_MON_NUM+1)*OVERWORLD_WILD_SPAWN_METADATA_MAX_FORM);
        input_size=header->exceptionsOffset+header->exceptionCount*sizeof(OverworldWildSpawnMetadataException);
        header->totalSize=input_size;
        OverworldWildSpawnMetadataException *exceptions=(void*)(input+header->exceptionsOffset);
        memset(exceptions,0,header->exceptionCount*sizeof(*exceptions));
        for(unsigned i=0;i<header->exceptionCount;i++) {
            exceptions[i].species=i/OVERWORLD_WILD_SPAWN_METADATA_MAX_FORM;
            exceptions[i].form=i%OVERWORLD_WILD_SPAWN_METADATA_MAX_FORM+1;
            exceptions[i].metadata.renderModePlusOne=1;
        }
        header->checksum=OverworldWildBehavior_SpawnMetadataChecksum(input,input_size);
        CHECK(OverworldWildBehavior_LoadSpawnMetadata());
        CHECK(allocs==1&&reads==1&&decodes==1);reset();
        input_size=TEST_CAP;boundary_only=TRUE;
        CHECK(OverworldWildBehavior_LoadSpawnMetadata());
        CHECK(allocs==1&&reads==1&&decodes==1);reset();
        input_size=TEST_CAP+1;
        CHECK(!OverworldWildBehavior_LoadSpawnMetadata());
        CHECK(!allocs&&!reads&&!decodes&&opens==1&&closes==1);CHECK(!terminal(0));reset();
        input_size=sizeof(*header)-1;
        CHECK(!OverworldWildBehavior_LoadSpawnMetadata());
        CHECK(!allocs&&!reads&&!decodes);CHECK(!terminal(0));
    } else if(!strcmp(argv[2],"failures")) {
        header->magic^=1;
        CHECK(!OverworldWildBehavior_LoadSpawnMetadata());
        CHECK(allocs==1&&reads==1&&decodes==1&&closes==1);CHECK(!terminal(1));reset();
        fail_alloc=TRUE;CHECK(!OverworldWildBehavior_LoadSpawnMetadata());
        CHECK(allocs==1&&!reads&&!decodes&&closes==1);CHECK(!terminal(0));reset();
        fail_open=TRUE;CHECK(!OverworldWildBehavior_LoadSpawnMetadata());
        CHECK(!allocs&&!reads&&!closes);CHECK(!terminal(0));reset();
        missing_member=TRUE;CHECK(!OverworldWildBehavior_LoadSpawnMetadata());
        CHECK(!allocs&&!reads&&closes==1);CHECK(!terminal(0));
    } else return 2;
    free(input);printf("PASS %s generatedBytes=%ld cap=%u\n",argv[2],size,(unsigned)TEST_CAP);return 0;
}
'''


class SpawnMetadataCapacityTests(unittest.TestCase):
    def test_persistent_catalogs_split_across_supported_heaps(self):
        from scripts.verify_overworld_spawn_profile_lifecycle import production_function
        header = (ROOT / "include/overworld_wild_behavior_data.h").read_text()
        self.assertRegex(header,
            r"#define\s+OVERWORLD_WILD_BEHAVIOR_DATA_HEAP_ID\s+HEAPID_WORLD")
        self.assertRegex(header,
            r"#define\s+OVERWORLD_WILD_SPAWN_METADATA_HEAP_ID\s+HEAPID_DEFAULT")
        metadata_loader = production_function(SOURCE.read_text(),
            "OverworldWildBehavior_LoadSpawnMetadata", "BOOL")
        behavior_loader = production_function(SPAWNS_SOURCE.read_text(),
            "OverworldWildSpawns_LoadCodeAddonBlob", "BOOL")
        self.assertEqual(metadata_loader.count("HEAPID_WORLD"), 1)
        self.assertEqual(
            metadata_loader.count("OVERWORLD_WILD_SPAWN_METADATA_HEAP_ID"), 1)
        self.assertEqual(behavior_loader.count("HEAPID_WORLD"), 1)
        self.assertEqual(
            behavior_loader.count("OVERWORLD_WILD_BEHAVIOR_DATA_HEAP_ID"), 1)

    def test_checksum_matches_byte_reference_for_all_lengths_and_alignments(self):
        from scripts.verify_overworld_spawn_profile_lifecycle import production_function
        body = production_function(SOURCE.read_text(),
            "OverworldWildBehavior_SpawnMetadataChecksum", "u32")
        unit = PRELUDE + body + r'''
int main(void) {
    u8 bytes[32772];
    for (u32 pattern=0;pattern<3;pattern++) {
        for (u32 i=0;i<sizeof(bytes);i++)
            bytes[i]=pattern==0?255:pattern==1?0:(u8)(i*73+(i>>8));
        for (u32 offset=0;offset<4;offset++) {
            u32 expected=0;
            for (u32 size=0;size<=32768;size++) {
                CHECK(OverworldWildBehavior_SpawnMetadataChecksum(bytes+offset,size)==expected);
                if (size<32||size>=36) expected+=bytes[offset+size];
            }
        }
    }
    return 0;
}
'''
        binary = Path(self.temp.name) / "checksum"
        self.compile_fixture(binary, unit)
        result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @staticmethod
    def compile_fixture(binary, source):
        result = subprocess.run([*shlex.split(os.environ.get("HOST_CC","cc")),
            "-std=c11","-O2","-Wall","-Wextra","-Werror","-I",str(ROOT/"include"),
            "-x","c","-","-o",str(binary)],input=source,text=True,capture_output=True,timeout=30)
        if result.returncode:
            raise RuntimeError(result.stderr)

    @classmethod
    def setUpClass(cls):
        if not BLOB.is_file():
            raise FileNotFoundError("generate build/OverworldWildSpawnMetadata.bin before the metadata capacity check")
        cls.temp = tempfile.TemporaryDirectory(prefix="spawn-metadata-capacity-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.binary = Path(cls.temp.name) / "capacity"
        cls.compile_fixture(cls.binary,harness())

    def check_case(self, case):
        result = subprocess.run([str(self.binary),str(BLOB),case],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_current_generated_blob_loads_and_lookup_does_not_fall_back(self):
        self.check_case("generated")

    def test_capacity_inclusive_guard_and_largest_valid_format(self):
        self.check_case("boundaries")

    def test_malformed_and_native_failures_free_once_and_latch(self):
        self.check_case("failures")

    def test_old_runtime_capacity_reproduces_generated_blob_rejection(self):
        binary=Path(self.temp.name)/"old-capacity"
        self.compile_fixture(binary,harness(cap_override=0x4000))
        result=subprocess.run([str(binary),str(BLOB),"generated-too-large"],
            capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        red=subprocess.run([str(binary),str(BLOB),"generated"],
            capture_output=True,text=True,timeout=10)
        self.assertNotEqual(red.returncode,0)
        self.assertIn("OverworldWildBehavior_LoadSpawnMetadata()",red.stderr)

    def test_generator_shared_capacity_boundary_and_old_cap(self):
        header=ROOT/"include/overworld_wild_behavior_data.h"
        cap=generator.parse_object_define(header.read_text(),
            "OVERWORLD_WILD_SPAWN_METADATA_MAX_BLOB_SIZE")
        generator.validate_runtime_capacity(bytes(cap),header,"at cap")
        with self.assertRaisesRegex(ValueError,"above runtime capacity"):
            generator.validate_runtime_capacity(bytes(cap+1),header,"above cap")
        blob=BLOB.read_bytes()
        generator.validate_runtime_capacity(blob,header,"current generated")
        old_header=Path(self.temp.name)/"old-cap.h"
        old_header.write_text("#define OVERWORLD_WILD_SPAWN_METADATA_MAX_BLOB_SIZE 0x4000\n")
        with self.assertRaisesRegex(ValueError,"above runtime capacity 16384"):
            generator.validate_runtime_capacity(blob,old_header,"old generated")
