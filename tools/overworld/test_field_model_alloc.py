"""Run the actual temporary model allocator against measured heap outcomes."""

from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HARNESS = r'''
#include <assert.h>
#include <stdlib.h>
#include "types.h"

void *OverworldFieldModel_AllocTemporary(u32 heapId, u32 size);

static unsigned calls;
static unsigned expectedCalls;
static unsigned budgetReads;
static unsigned expectedBudgetReads;
static u32 requestedSize;
static u32 freeBytes;
static void *answers[2];
static unsigned char originalBlock, fallbackBlock;

#define EXPECTED_FIELD_RESERVE (20u * 1024u + 64u)

void *sys_AllocMemoryLo(u32 heapId, u32 size)
{
    unsigned index = calls++;
    assert(index < expectedCalls);
    assert(heapId == (index == 0 ? 4u : 11u));
    assert(size == requestedSize);
    if (index == 1) {
        assert(budgetReads == 1);
    }
    return answers[index];
}

u32 GF_ExpHeap_FndGetTotalFreeSize(u32 heapId)
{
    assert(heapId == 11);
    assert(calls == 1 && answers[0] == NULL);
    assert(++budgetReads <= expectedBudgetReads);
    return freeBytes;
}

/* Allocation failure must return to its caller, never read a file into NULL. */
void NARC_ReadWholeMember(void *narc, u32 member, void *dest)
{
    (void)narc;
    (void)member;
    (void)dest;
    assert(!"allocator attempted an archive read");
}

int main(int argc, char **argv)
{
    int mode;
    void *expected;
    assert(argc == 3);
    mode = atoi(argv[1]);
    requestedSize = (u32)strtoul(argv[2], NULL, 10);
    switch (mode) {
    case 0: /* FIELD1 has room: preserve the original stock allocation. */
        answers[0] = &originalBlock;
        answers[1] = &fallbackBlock;
        expected = &originalBlock;
        expectedCalls = 1;
        expectedBudgetReads = 0;
        freeBytes = 0;
        break;
    case 1: /* Exact reserve boundary permits the same request in FIELD2. */
        answers[0] = NULL;
        answers[1] = &fallbackBlock;
        expected = &fallbackBlock;
        expectedCalls = 2;
        expectedBudgetReads = 1;
        freeBytes = requestedSize + EXPECTED_FIELD_RESERVE;
        break;
    case 2: /* No memory in either heap: do not invent a pointer or retry. */
        answers[0] = NULL;
        answers[1] = NULL;
        expected = NULL;
        expectedCalls = 2;
        expectedBudgetReads = 1;
        freeBytes = requestedSize + EXPECTED_FIELD_RESERVE;
        break;
    case 3: /* One byte short must not consume the script reserve. */
        answers[0] = NULL;
        answers[1] = &fallbackBlock;
        expected = NULL;
        expectedCalls = 1;
        expectedBudgetReads = 1;
        freeBytes = requestedSize + EXPECTED_FIELD_RESERVE - 1;
        break;
    case 4: /* Guard subtraction so a small free size cannot wrap to huge. */
        answers[0] = NULL;
        answers[1] = &fallbackBlock;
        expected = NULL;
        expectedCalls = 1;
        expectedBudgetReads = 1;
        freeBytes = EXPECTED_FIELD_RESERVE - 1;
        break;
    default:
        assert(!"unknown test case");
        return 1;
    }
    assert(OverworldFieldModel_AllocTemporary(4, requestedSize) == expected);
    assert(calls == expectedCalls);
    assert(budgetReads == expectedBudgetReads);
    return 0;
}
'''


class FieldModelAllocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = tempfile.TemporaryDirectory(prefix="field-model-alloc-")
        cls.addClassCleanup(directory.cleanup)
        temporary = Path(directory.name)
        harness = temporary / "harness.c"
        harness.write_text(HARNESS)
        cls.binary = temporary / "field-model-alloc"
        result = subprocess.run([
            *shlex.split(os.environ.get("CC", "cc")), "-std=c99", "-Wall", "-Wextra",
            "-Werror", "-Wno-attributes", "-Wno-macro-redefined",
            # The product's ELF section and ARM attributes have no host meaning.
            "-fno-builtin", "-D__attribute__(x)=",
            "-I", str(ROOT / "include"),
            str(ROOT / "lib/overworld/overworld_field_model_alloc.c"),
            str(harness), "-o", str(cls.binary),
        ], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)

    def run_case(self, mode):
        # Both sizes occurred in the real Goldenrod/Route34 crossing. Keeping
        # them exact rejects zero-sized, truncated, or padded fallback requests.
        for size in (6760, 13352):
            with self.subTest(size=size):
                result = subprocess.run([str(self.binary), str(mode), str(size)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_original_heap_success_never_uses_fallback(self):
        self.run_case(0)

    def test_original_heap_failure_retries_same_size_in_field2(self):
        self.run_case(1)

    def test_both_heaps_fail_returns_null_without_reading_a_file(self):
        self.run_case(2)

    def test_one_byte_below_fallback_budget_keeps_script_reserve(self):
        self.run_case(3)

    def test_free_space_below_reserve_cannot_wrap_budget(self):
        self.run_case(4)


if __name__ == "__main__":
    unittest.main()
