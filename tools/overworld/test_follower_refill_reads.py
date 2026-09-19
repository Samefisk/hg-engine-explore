"""Exercise the production follower identity check and its native lock scope."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools.overworld.test_spawn_spatial import extract_function

ROOT = Path(__file__).resolve().parents[2]


class FollowerRefillReadsTests(unittest.TestCase):
    def test_matching_and_each_rejection_release_only_the_owned_lock(self):
        source = (ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c").read_text()
        body = extract_function(source, "OverworldWildSpawns_FollowerMatchesSelection", "BOOL")
        harness = r'''
#include <assert.h>
#include <stddef.h>
typedef int BOOL;
typedef unsigned char u8;
#define TRUE 1
#define FALSE 0
#define OW_WILD_FOLLOWER_SLOT 0
enum { MON_DATA_SPECIES, MON_DATA_FORM, MON_DATA_LEVEL, MON_DATA_PERSONALITY };
struct PartyPokemon { int values[4], shiny, locked; };
typedef struct { int active, species, form, level, personality, shiny; } OverworldWildSpawn;
typedef struct { OverworldWildSpawn spawns[1]; int activeFollowerPartySlot; } OverworldWildSpawnState;
static int acquires, releases, reads, incoming;
static BOOL OverworldWildSpawns_AcquireMonLock(struct PartyPokemon *mon) {
    acquires++; incoming = mon->locked; mon->locked = TRUE; return !incoming;
}
static BOOL OverworldWildSpawns_ReleaseMonLock(struct PartyPokemon *mon, BOOL token) {
    releases++; assert(token == !incoming && mon->locked);
    if (token) mon->locked = FALSE;
    return token;
}
static int OverworldWildSpawns_ReadMonData(struct PartyPokemon *mon, int field, void *unused) {
    (void)unused; assert(mon->locked); reads++; return mon->values[field];
}
static int OverworldWildSpawns_MonIsShiny(struct PartyPokemon *mon) {
    assert(mon->locked); reads++; return mon->shiny;
}
''' + body + r'''
int main(void) {
    for (int locked = 0; locked < 2; locked++) {
        for (int mismatch = -3; mismatch < 5; mismatch++) {
            OverworldWildSpawnState state = {{{1, 155, 0, 12, 456, 0}}, 2};
            struct PartyPokemon mon = {{155, 0, 12, 456}, 0, locked};
            if (mismatch == -3) state.spawns[0].active = 0;
            if (mismatch == -2) state.activeFollowerPartySlot = 1;
            if (mismatch >= 0 && mismatch < 4) mon.values[mismatch]++;
            if (mismatch == 4) mon.shiny = 1;
            acquires = releases = reads = 0;
            assert(OverworldWildSpawns_FollowerMatchesSelection(&state, &mon, 2) == (mismatch == -1));
            assert(mon.locked == locked);
            assert(acquires == (mismatch >= -1) && releases == acquires);
            assert(reads == (mismatch < -1 ? 0 : mismatch == -1 ? 5 : mismatch + 1));
        }
    }
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix="follower-refill-") as directory:
            path = Path(directory)
            (path / "test.c").write_text(harness)
            subprocess.run(["cc", "-std=c99", "-Wall", "-Werror", str(path / "test.c"),
                            "-o", str(path / "test")], check=True, capture_output=True)
            subprocess.run([str(path / "test")], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
