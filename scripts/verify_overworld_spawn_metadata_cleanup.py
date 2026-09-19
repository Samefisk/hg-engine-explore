#!/usr/bin/env python3
"""Host execution of the actual metadata cleanup C body; no ROM/game proof."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/overworld_wild_behavior_data_overlay/overworld_wild_behavior_data_overlay.c"
NAME = "OverworldWildBehavior_CleanupSpawnMetadata"


def cleanup_body():
    spec = importlib.util.spec_from_file_location(
        "spawn_cleanup_extract", ROOT / "scripts/verify_overworld_spawn_profile_lifecycle.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper.production_function(SOURCE.read_text(), NAME, "void")


def harness_source(body):
    return r'''
#include <stdint.h>
#include <stdio.h>
#include <stddef.h>
typedef uint32_t u32;
typedef int BOOL;
#define FALSE 0
#define TRUE 1
static void *sOverworldWildSpawnMetadataBlob;
static u32 sOverworldWildSpawnMetadataBlobSize;
static BOOL sOverworldWildSpawnMetadataLoadAttempted;
static unsigned calls, null_frees, unexpected_frees;
static unsigned char token;

/* Stock Heap_Free dereferences the allocation header even for NULL. A host
 * libc free(NULL) would conceal the bug, so model that exact precondition. */
static void sys_FreeMemoryEz(void *pointer)
{
    ++calls;
    if (pointer == NULL) ++null_frees;
    else if (pointer != &token) ++unexpected_frees;
}
''' + body + r'''

static int check(const char *name, unsigned expected_calls)
{
    if (calls != expected_calls || null_frees || unexpected_frees
        || sOverworldWildSpawnMetadataBlob != NULL
        || sOverworldWildSpawnMetadataBlobSize != 0
        || sOverworldWildSpawnMetadataLoadAttempted != FALSE) {
        fprintf(stderr, "metadata cleanup invariant failed: %s; calls=%u expected=%u null=%u wrong=%u\n",
                name, calls, expected_calls, null_frees, unexpected_frees);
        return 1;
    }
    printf("PASS %s\n", name);
    return 0;
}

int main(void)
{
    int failures = 0;
    /* Never allocated: boot teardown and repeated teardown must be harmless. */
    OverworldWildBehavior_CleanupSpawnMetadata();
    OverworldWildBehavior_CleanupSpawnMetadata();
    failures += check("never allocated, repeated cleanup", 0);

    /* Failed loading can set metadata flags without owning an allocation. */
    calls = null_frees = unexpected_frees = 0;
    sOverworldWildSpawnMetadataBlob = NULL;
    sOverworldWildSpawnMetadataBlobSize = 123;
    sOverworldWildSpawnMetadataLoadAttempted = TRUE;
    OverworldWildBehavior_CleanupSpawnMetadata();
    failures += check("failed allocation resets metadata without free", 0);

    /* No real allocation is needed to prove exact ownership and one free. */
    calls = null_frees = unexpected_frees = 0;
    sOverworldWildSpawnMetadataBlob = &token;
    sOverworldWildSpawnMetadataBlobSize = 123;
    sOverworldWildSpawnMetadataLoadAttempted = TRUE;
    OverworldWildBehavior_CleanupSpawnMetadata();
    failures += check("owned allocation freed once", 1);
    OverworldWildBehavior_CleanupSpawnMetadata();
    failures += check("second cleanup does not free again", 1);
    return failures ? 1 : 0;
}
'''


def execute(body):
    with tempfile.TemporaryDirectory(prefix="spawn-metadata-cleanup-") as directory:
        binary = Path(directory) / "cleanup"
        command = [*shlex.split(os.environ.get("HOST_CC", "cc")), "-std=c11", "-O2",
                   "-Wall", "-Wextra", "-Werror", "-x", "c", "-", "-o", str(binary)]
        compiled = subprocess.run(command, input=harness_source(body), capture_output=True,
                                  text=True, timeout=30)
        if compiled.returncode:
            raise RuntimeError("metadata cleanup host compile failed:\n" + compiled.stderr)
        return subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)


def without_null_guard(body):
    pattern = r"\bif\s*\(\s*sOverworldWildSpawnMetadataBlob\s*(?:!=\s*NULL\s*)?\)"
    mutant, count = re.subn(pattern, "if (1)", body)
    if count != 1:
        raise ValueError("expected one metadata NULL guard for the guard-removal control")
    return mutant


def main():
    body = cleanup_body()
    baseline = execute(body)
    print(baseline.stdout + baseline.stderr, end="")
    if baseline.returncode:
        return 1
    mutant = execute(without_null_guard(body))
    if mutant.returncode != 1 or "metadata cleanup invariant failed" not in mutant.stderr \
            or "null=2" not in mutant.stderr:
        raise RuntimeError("guard-removal control did not reproduce the NULL-free failure")
    print("PASS removed NULL guard rejected by the same C harness")
    print("PASS actual C cleanup only; ARM runtime and game behavior remain separate proof")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
