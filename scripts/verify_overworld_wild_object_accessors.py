#!/usr/bin/env python3
"""Host equivalence for the Wild adapter's four stock object accessors.

This is an ABI/code-size check, not evidence of gameplay behavior. Stock
map_object.c implements these as two word reads and flags OR/AND-NOT. Like
stock, the local functions require a live, non-null object.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
ACCESSORS = {
    "OverworldWildSpawns_ObjectCurrentX": "u32",
    "OverworldWildSpawns_ObjectCurrentY": "u32",
    "OverworldWildSpawns_SetObjectFlags": "void",
    "OverworldWildSpawns_ClearObjectFlags": "void",
}


def accessor_source(source: str) -> str:
    result = []
    for name, result_type in ACCESSORS.items():
        match = re.search(
            rf"static inline __attribute__\(\(always_inline\)\) {result_type}\s+"
            rf"{name}\s*\([^{{]+\)\s*\{{[^{{}}]+\}}", source)
        if match is None:
            raise SystemExit(f"missing typed stock accessor: {name}")
        result.append(match.group(0))
    for stock in ("MapObject_GetCurrentX", "MapObject_GetCurrentY",
                  "MapObject_SetBits", "MapObject_ClearBits"):
        if re.search(rf"\b{stock}\s*\(", source):
            raise SystemExit(f"Wild adapter still emits a stock long call: {stock}")
    return "\n".join(result)


def main() -> None:
    source = SOURCE.read_text()
    functions = accessor_source(source)
    header = (ROOT / "include/map_events_internal.h").read_text()
    prefix = re.search(r"struct LocalMapObject \{.*?/\*0x06C\*/ int yCurr;",
                       header, re.S)
    if prefix is None:
        raise SystemExit("engine LocalMapObject coordinate layout changed")
    harness = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
typedef uint32_t u32;
typedef uint16_t u16;
typedef uint8_t u8;
typedef struct LocalMapObject LocalMapObject;
STRUCT_PREFIX
};
_Static_assert(sizeof(int) == 4, "engine word width");
_Static_assert(offsetof(LocalMapObject, flags) == 0, "stock flags offset");
_Static_assert(offsetof(LocalMapObject, xCurr) == 0x64, "stock X offset");
_Static_assert(offsetof(LocalMapObject, yCurr) == 0x6C, "stock Z offset");
FUNCTIONS
int main(void) {
    static const u32 words[] = {0, 1, 0x7FFF, 0xFFFF, 0x10000,
        0x7FFFFFFF, 0x80000000, 0x80000001, 0xAAAAAAAA, 0xFFFFFFFF};
    for (unsigned i = 0; i < sizeof(words) / sizeof(words[0]); i++) {
        for (unsigned j = 0; j < sizeof(words) / sizeof(words[0]); j++) {
            LocalMapObject object, expected;
            memset(&object, 0xA5, sizeof(object));
            memcpy((u8 *)&object + 0x64, &words[i], 4);
            memcpy((u8 *)&object + 0x6C, &words[j], 4);
            expected = object;
            assert(OverworldWildSpawns_ObjectCurrentX(&object) == words[i]);
            assert(OverworldWildSpawns_ObjectCurrentY(&object) == words[j]);
            assert(memcmp(&object, &expected, sizeof(object)) == 0);
            object.flags = words[i];
            expected = object;
            expected.flags = words[i] | words[j];
            OverworldWildSpawns_SetObjectFlags(&object, words[j]);
            assert(memcmp(&object, &expected, sizeof(object)) == 0);
            object.flags = words[i];
            expected = object;
            expected.flags = words[i] & ~words[j];
            OverworldWildSpawns_ClearObjectFlags(&object, words[j]);
            assert(memcmp(&object, &expected, sizeof(object)) == 0);
        }
    }
    return 0;
}
'''.replace("STRUCT_PREFIX", prefix.group(0))
    mutations = {
        "wrong coordinate": functions.replace("(u32)object->xCurr", "(u32)object->yCurr"),
        "truncated coordinate": functions.replace("(u32)object->xCurr", "(u16)object->xCurr"),
        "flags overwritten": functions.replace("object->flags |= bits", "object->flags = bits"),
        "wrong clear mask": functions.replace("object->flags &= ~bits", "object->flags &= bits"),
    }
    with tempfile.TemporaryDirectory(prefix="ow-wild-accessors-") as temp:
        work = Path(temp)
        for label, candidate in [("baseline", functions), *mutations.items()]:
            if label != "baseline" and candidate == functions:
                raise SystemExit(f"negative control did not mutate source: {label}")
            path = work / "accessors.c"
            path.write_text(harness.replace("FUNCTIONS", candidate))
            binary = work / "accessors"
            subprocess.run([*shlex.split(os.environ.get("CC", "cc")), "-std=c11",
                            "-Wall", "-Wextra", "-Werror", str(path), "-o", str(binary)],
                           check=True, capture_output=True, text=True)
            completed = subprocess.run([str(binary)], cwd=work, capture_output=True)
            if (completed.returncode == 0) != (label == "baseline"):
                raise SystemExit(f"accessor equivalence result is wrong: {label}")
    print("Wild object accessors: 100 coordinate/flag pairs and four mutations passed")


if __name__ == "__main__":
    main()
