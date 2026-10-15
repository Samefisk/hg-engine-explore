"""S0 source contracts for the spawn-time frame-cost fixes (TKT-0076).

These pin the structure that keeps natural population work inside the game
loop. They are checker controls, not gameplay proof: the registered
`population.route30.saturated-headroom` run owns the measured claim and
`test_spawn_move_entry` executes the idle-search behavior.
"""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.overworld.test_spawn_refill_budget import extract_function

WILD = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"
CONTACT = ROOT / "src/player_health_contact.c"


def squash(text):
    return "".join(text.split())


def verify_frame_defers_new_actor(source):
    frame = squash(extract_function(source, "OverworldWildSpawns_FrameMovementTask", "void"))
    read = "intcommittedSlot=runtime->queuedSpawnSlotPlusOne-1;"
    commit = "OverworldWildSpawns_CommitQueuedSpawn(state,fieldSystem);"
    created = "if(state->spawns[committedSlot].active){newlyCreatedMask=(u16)(1u<<committedSlot);}"
    owner = "|newlyCreatedMask;"
    for needle in (read, commit, created, owner):
        if frame.count(needle) != 1:
            raise AssertionError("new-actor deferral lost: " + needle)
    if not frame.index(read) < frame.index(commit) < frame.index(created):
        raise AssertionError("created slot must be read before and checked after the commit")
    mask = frame.index("roleOwnedMask=")
    if not frame.index(owner) > mask or "heavyWorkMask=(u16)(frameWork>>" not in frame[mask:]:
        raise AssertionError("deferred slot must leave this update's movement masks")
    if frame.index(created) > mask:
        raise AssertionError("deferral must be known before the movement masks are built")


def verify_idle_search_is_bounded(source):
    tick = squash(extract_function(source, "OverworldWildSpawns_TickMovementParams", "void"))
    cap = "if(idleIntentsIssued>=OW_WILD_SPAWNER_IDLE_INTENTS_PER_UPDATE){continue;}idleIntentsIssued++;"
    issue = "OverworldWildSpawns_IssueIdleIntent(state,fieldSystem,i,object,&profile,&primitives)"
    rest = ("if(state->movementCooldowns[i]==0"
            "&&!OverworldWildSpawns_IsMovementSlotInProgress(state,i)){"
            "state->movementCooldowns[i]="
            "OverworldWildSpawns_GetActiveConditionApplications(state,i)==0"
            "?OW_WILD_SPAWNER_IDLE_RETRY_REST_FRAMES"
            ":OW_WILD_SPAWNER_IDLE_CONDITION_REST_FRAMES;}")
    for needle in (cap, issue, rest):
        if tick.count(needle) != 1:
            raise AssertionError("idle search bound lost: " + needle[:60])
    if not tick.index(cap) < tick.index(issue) < tick.index(rest):
        raise AssertionError("the rest must follow a search that started nothing")
    if tick.index("OverworldWildSpawns_ResolveConditionsAtIntentBoundary(") > tick.index(issue):
        raise AssertionError("Condition evaluation must still precede the idle decision")


def verify_constants(source):
    for name, value in (("OW_WILD_SPAWNER_IDLE_RETRY_REST_FRAMES", 8),
                        ("OW_WILD_SPAWNER_IDLE_CONDITION_REST_FRAMES", 4),
                        ("OW_WILD_SPAWNER_IDLE_INTENTS_PER_UPDATE", 1)):
        found = re.findall(r"#define\s+%s\s+(\d+)\b" % name, source)
        if found != [str(value)]:
            raise AssertionError("%s must stay %d (found %s)" % (name, value, found))


def verify_sparse_refill_is_fast(source):
    apply = squash(extract_function(source, "OverworldWildSpawns_ApplyRefillDelay", "void"))
    clamp = ("if(delay>OW_WILD_REFILL_SPARSE_INTERVAL_FRAMES"
             "&&delay<OW_WILD_REFILL_BASE_INTERVAL_FRAMES*OW_WILD_REFILL_FULL_DENSITY_COUNT)"
             "delay=OW_WILD_REFILL_SPARSE_INTERVAL_FRAMES;")
    if apply.count(clamp) != 1:
        raise AssertionError("sparse refill clamp lost (waits below four times the Base)")
    for name, value in (("OW_WILD_REFILL_BASE_INTERVAL_FRAMES", 60),
                        ("OW_WILD_REFILL_FULL_DENSITY_COUNT", 4),
                        ("OW_WILD_REFILL_SPARSE_INTERVAL_FRAMES", 8)):
        found = re.findall(r"#define\s+%s\s+(\d+)\b" % name, source)
        if found != [str(value)]:
            raise AssertionError("%s must stay %d (found %s)" % (name, value, found))


def verify_contact_predicate(source):
    start = source.index("static BOOL COMBAT_CODE CombatContact_Current(")
    body = squash(source[start:source.index("\nvoid COMBAT_CODE PlayerHealthContact_BeginFrame(", start)])
    if "GetMapObjectByID" in body:
        raise AssertionError("contact validity must not scan the object array")
    generation = body.index("OVERWORLD_ACTOR_FIELD_CONTEXT_MAP_GENERATION(")
    if generation > body.index("spawn->object->id==spawn->objectId"):
        raise AssertionError("the Field generation gate must precede the object read")
    for needle in ("spawn->object->id==spawn->objectId",
                   "(spawn->object->flags&MAPOBJECTFLAG_ACTIVE)!=0"):
        if body.count(needle) != 1:
            raise AssertionError("contact ownership proof lost: " + needle)


class PopulationCostContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wild = WILD.read_text()
        cls.contact = CONTACT.read_text()

    def test_current_sources_satisfy_every_contract(self):
        verify_frame_defers_new_actor(self.wild)
        verify_idle_search_is_bounded(self.wild)
        verify_constants(self.wild)
        verify_sparse_refill_is_fast(self.wild)
        verify_contact_predicate(self.contact)

    def test_controls_reject_each_removed_guard(self):
        controls = (
            (verify_frame_defers_new_actor, self.wild,
             ("        : 0) | newlyCreatedMask;", "        : 0);"),
             ("newlyCreatedMask = (u16)(1u << committedSlot);", "newlyCreatedMask = 0;")),
            (verify_idle_search_is_bounded, self.wild,
             ("idleIntentsIssued >= OW_WILD_SPAWNER_IDLE_INTENTS_PER_UPDATE", "idleIntentsIssued >= 255"),
             ("                        : OW_WILD_SPAWNER_IDLE_CONDITION_REST_FRAMES;",
              "                        : 0;"),
             ("&& !OverworldWildSpawns_IsMovementSlotInProgress(state, i)) {\n                state->movementCooldowns[i] =",
              ") {\n                state->movementCooldowns[i] =")),
            (verify_constants, self.wild,
             ("#define OW_WILD_SPAWNER_IDLE_RETRY_REST_FRAMES 8",
              "#define OW_WILD_SPAWNER_IDLE_RETRY_REST_FRAMES 1")),
            (verify_sparse_refill_is_fast, self.wild,
             ("#define OW_WILD_REFILL_SPARSE_INTERVAL_FRAMES 8",
              "#define OW_WILD_REFILL_SPARSE_INTERVAL_FRAMES 60"),
             ("OW_WILD_REFILL_BASE_INTERVAL_FRAMES*OW_WILD_REFILL_FULL_DENSITY_COUNT",
              "0")),
            (verify_contact_predicate, self.contact,
             ("&& spawn->object->id == spawn->objectId",
              "&& GetMapObjectByID(field->mapObjectMan, spawn->objectId) == spawn->object")),
        )
        for verify, source, *mutations in controls:
            for old, new in mutations:
                with self.subTest(verify=verify.__name__, mutation=old[:40]):
                    self.assertIn(old, source)
                    with self.assertRaises(AssertionError):
                        verify(source.replace(old, new, 1))


if __name__ == "__main__":
    unittest.main()
