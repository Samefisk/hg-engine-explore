"""Exercise the actual catalog loader/getter after temporary memory pressure."""

from pathlib import Path
import os
import re
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


def actual_function(source, name, returns):
    matches = list(re.finditer(r"(?m)^static\b[^;{}]*?\b" + re.escape(name)
                              + r"\s*\([^;{}]*\)\s*\{", source))
    if len(matches) != 1:
        raise AssertionError("Expected one actual function: " + name)
    match = matches[0]
    depth = 1
    for end in range(match.end(), len(source)):
        depth += (source[end] == "{") - (source[end] == "}")
        if not depth:
            start = source.index(name, match.start(), match.end())
            return "static " + returns + " " + source[start:end + 1]
    raise AssertionError("Unclosed actual function: " + name)


PRELUDE = r'''
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include "overworld_wild_behavior_data.h"
#include "constants/file.h"

static void *sOverworldWildBehaviorDataBlob;
static BOOL sOverworldWildBehaviorDataLoadAttempted;
static void *gFieldSysPtr = (void *)1;
static OverworldWildBehaviorDataBlob blobStorage;
static unsigned freeChecks, archiveOpens, archiveCloses, allocations, reads, frees;
static unsigned queries, decodes;
static u32 freeBytes, memberSize, memberCount, requestedMember, expectedHeap;
static BOOL narcFail, allocationFail, decodeAllowed;
static int narcStorage, queryStorage;

u32 OverworldWildSpawns_FreeHeapBytes(u32 heapId)
{
    assert(heapId == expectedHeap);
    freeChecks++;
    return freeBytes;
}
void *NARC_ctor(u32 archive, u32 heapId)
{
    assert(archive == ARC_CODE_ADDONS && heapId == expectedHeap);
    archiveOpens++;
    return narcFail ? NULL : &narcStorage;
}
u16 NARC_GetFileCount(void *narc)
{
    assert(narc == &narcStorage);
    return memberCount;
}
u32 NARC_GetMemberSize(void *narc, u32 member)
{
    assert(narc == &narcStorage && member == requestedMember);
    return memberSize;
}
void NARC_dtor(void *narc)
{
    assert(narc == &narcStorage);
    archiveCloses++;
}
void *sys_AllocMemory(u32 heapId, u32 size)
{
    assert(heapId == expectedHeap && size == sizeof(blobStorage));
    allocations++;
    return allocationFail ? NULL : &blobStorage;
}
void NARC_ReadWholeMember(void *narc, u32 member, void *dest)
{
    assert(narc == &narcStorage && member == requestedMember);
    assert(dest == &blobStorage);
    reads++;
}
void sys_FreeMemoryEz(void *buffer)
{
    assert(buffer == &blobStorage);
    frees++;
}
static void *OverworldWildSpawns_QueryAddon(void *field, void *unused)
{
    assert(field == gFieldSysPtr && unused == NULL);
    queries++;
    return &queryStorage;
}
static BOOL OverworldWildSpawns_DecodeBehaviorDataBlob(void)
{
    assert(sOverworldWildBehaviorDataBlob == &blobStorage);
    decodes++;
    return decodeAllowed;
}
'''

DRIVER = r'''
static void Reset(void)
{
    sOverworldWildBehaviorDataBlob = NULL;
    sOverworldWildBehaviorDataLoadAttempted = FALSE;
    freeChecks = archiveOpens = archiveCloses = allocations = reads = frees = 0;
    queries = decodes = 0;
    freeBytes = sizeof(blobStorage) + OVERWORLD_FIELD_QUERY_HEAP_RESERVE;
    memberSize = sizeof(blobStorage);
    memberCount = 100;
    requestedMember = CODE_ADDON_OVERWORLD_WILD_BEHAVIOR_DATA;
    expectedHeap = OVERWORLD_WILD_BEHAVIOR_DATA_HEAP_ID;
    narcFail = allocationFail = FALSE;
    decodeAllowed = TRUE;
}
static void ExpectCachedSuccess(void)
{
    unsigned checks, opens, allocs, readCount, queryCount, decodeCount;
    assert(OverworldWildSpawns_GetBehaviorDataBlob() == &blobStorage);
    assert(sOverworldWildBehaviorDataLoadAttempted == TRUE);
    assert(reads == 1 && decodes == 1 && frees == 0);
    checks = freeChecks; opens = archiveOpens; allocs = allocations;
    readCount = reads; queryCount = queries; decodeCount = decodes;
    assert(OverworldWildSpawns_GetBehaviorDataBlob() == &blobStorage);
    assert(freeChecks == checks && archiveOpens == opens && allocations == allocs);
    assert(reads == readCount && queries == queryCount && decodes == decodeCount);
}
static void ExpectLatchedFailure(void)
{
    unsigned checks = freeChecks, opens = archiveOpens, allocs = allocations;
    unsigned readCount = reads, queryCount = queries, decodeCount = decodes;
    assert(sOverworldWildBehaviorDataLoadAttempted == TRUE);
    assert(sOverworldWildBehaviorDataBlob == NULL);
    memberCount = 100;
    memberSize = sizeof(blobStorage);
    decodeAllowed = TRUE;
    assert(OverworldWildSpawns_GetBehaviorDataBlob() == NULL);
    assert(freeChecks == checks && archiveOpens == opens && allocations == allocs);
    assert(reads == readCount && queries == queryCount && decodes == decodeCount);
}
int main(int argc, char **argv)
{
    int mode;
    assert(argc == 2);
    mode = atoi(argv[1]);
    Reset();
    switch (mode) {
    case 0: /* Pending native textures temporarily consume the catalog budget. */
        freeBytes--;
        assert(OverworldWildSpawns_GetBehaviorDataBlob() == NULL);
        assert(!sOverworldWildBehaviorDataLoadAttempted);
        assert(archiveOpens == 0 && reads == 0 && decodes == 0);
        freeBytes++;
        ExpectCachedSuccess();
        assert(queries == 2 && freeChecks == 2 && archiveOpens == 1);
        break;
    case 1: /* Archive handle allocation can recover without reloading Field. */
        narcFail = TRUE;
        assert(OverworldWildSpawns_GetBehaviorDataBlob() == NULL);
        assert(!sOverworldWildBehaviorDataLoadAttempted);
        assert(archiveOpens == 1 && archiveCloses == 0 && reads == 0);
        narcFail = FALSE;
        ExpectCachedSuccess();
        assert(archiveOpens == 2 && archiveCloses == 1);
        break;
    case 2: /* Total free bytes can suffice while no contiguous block fits. */
        allocationFail = TRUE;
        assert(OverworldWildSpawns_GetBehaviorDataBlob() == NULL);
        assert(!sOverworldWildBehaviorDataLoadAttempted);
        assert(allocations == 1 && archiveCloses == 1 && reads == 0);
        allocationFail = FALSE;
        ExpectCachedSuccess();
        assert(allocations == 2 && archiveOpens == archiveCloses);
        break;
    case 3: /* Missing members and corrupt sizes must not retry each frame. */
    case 4:
    case 5:
        if (mode == 3) memberCount = requestedMember;
        if (mode == 4) memberSize = 0;
        if (mode == 5) memberSize--;
        assert(OverworldWildSpawns_GetBehaviorDataBlob() == NULL);
        assert(archiveCloses == 1 && allocations == 0 && reads == 0);
        ExpectLatchedFailure();
        break;
    case 6: /* A decoder failure frees once and stays latched. */
        decodeAllowed = FALSE;
        assert(OverworldWildSpawns_GetBehaviorDataBlob() == NULL);
        assert(reads == 1 && decodes == 1 && frees == 1);
        ExpectLatchedFailure();
        assert(frees == 1);
        break;
    case 7: /* Query add-on memory failures do not clear the catalog latch. */
        requestedMember = OVERWORLD_QUERY_CODE_ADDON_MEMBER_ID;
        expectedHeap = HEAPID_WORLD;
        for (unsigned fault = 0; fault < 3; fault++) {
            void *output = NULL;
            sOverworldWildBehaviorDataLoadAttempted = TRUE;
            freeBytes = sizeof(blobStorage) + OVERWORLD_FIELD_QUERY_HEAP_RESERVE;
            narcFail = allocationFail = FALSE;
            if (fault == 0) freeBytes--;
            if (fault == 1) narcFail = TRUE;
            if (fault == 2) allocationFail = TRUE;
            assert(!OverworldWildSpawns_LoadCodeAddonBlob(requestedMember,
                sizeof(blobStorage), &output, NULL));
            assert(output == NULL && sOverworldWildBehaviorDataLoadAttempted);
        }
        break;
    case 8: /* Successful load has no archive or decode work on later gets. */
        ExpectCachedSuccess();
        assert(archiveOpens == 1 && archiveCloses == 1 && allocations == 1);
        break;
    default:
        assert(!"Unknown test case");
        return 1;
    }
    return 0;
}
'''


class BehaviorBlobRetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = SOURCE.read_text()
        macros = []
        for filename, name in (
                ("overworld_query_code_addon.h", "OVERWORLD_QUERY_CODE_ADDON_MEMBER_ID"),
                ("overworld_cargo_query_wild.h", "OVERWORLD_FIELD_QUERY_HEAP_RESERVE")):
            header = (ROOT / "include" / filename).read_text()
            macros.append(re.search(r"^#define " + name + r"[^\n]+", header, re.M).group(0))
        bodies = [actual_function(source, "OverworldWildSpawns_LoadCodeAddonBlob", "BOOL"),
                  actual_function(source, "OverworldWildSpawns_GetBehaviorDataBlob",
                                  "const OverworldWildBehaviorDataBlob *")]
        directory = tempfile.TemporaryDirectory(prefix="behavior-blob-retry-")
        cls.addClassCleanup(directory.cleanup)
        temporary = Path(directory.name)
        harness = temporary / "retry.c"
        harness.write_text("\n".join([*macros, PRELUDE, *bodies, DRIVER]))
        cls.binary = temporary / "retry"
        result = subprocess.run([
            *shlex.split(os.environ.get("CC", "cc")), "-std=c11", "-Wall", "-Wextra",
            "-Werror", "-Wno-attributes", "-Wno-macro-redefined", "-Wno-pointer-to-int-cast",
            "-DOVERWORLD_BEHAVIOR_HOST",
            "-I", str(ROOT / "include"), str(harness), "-o", str(cls.binary),
        ], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def check_case(self, mode):
        result = subprocess.run([str(self.binary), str(mode)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_catalog_retries_after_temporary_budget_shortage(self):
        self.check_case(0)

    def test_catalog_retries_after_archive_handle_memory_failure(self):
        self.check_case(1)

    def test_catalog_retries_after_contiguous_allocation_failure(self):
        self.check_case(2)

    def test_bad_member_or_size_stays_latched(self):
        for mode in (3, 4, 5):
            with self.subTest(mode=mode):
                self.check_case(mode)

    def test_decoder_failure_frees_once_and_stays_latched(self):
        self.check_case(6)

    def test_query_resource_failure_does_not_clear_catalog_latch(self):
        self.check_case(7)

    def test_loaded_catalog_is_cached_without_more_reads(self):
        self.check_case(8)


if __name__ == "__main__":
    unittest.main()
