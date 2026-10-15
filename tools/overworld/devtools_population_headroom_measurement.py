"""Saturated Route 30 pond-bank game-loop headroom through the existing readers.

TKT-0076: real wild spawning cost frames on Route 30, worst near the pond bank
where little grass is close. A late loop only shows the failure after the loop
has already overrun. This measurement also reads the loop's idle headroom, the
ticks the main loop spends in its mandatory VBlank wait (return clock minus
entry clock of that wait), so a loop that is close to late is visible.

No recorder, input driver or native observer lives here. The shared main-loop
reader supplies one row per loop; prepared spawn rows keep their native events.
Prepared setup (teleport, six Wild spawns) earns no credit. Natural refill, the
population cap, profiles and timers are never overridden.
"""
from copy import deepcopy

from tools.overworld.devtools_main_loop_probe import (
    ENTRY_SITE,
    MAX_ZERO_STUTTER_ARM9_TICKS,
    NORMAL_MAIN_LOOP_NATIVE_CYCLES,
    RETURN_SITE,
    SCOPE,
    WAIT_SCOPE,
    MainLoopProbe,
)
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import engine_binding_identity, select_current_actor

KIND = "population-headroom-v1"
REQUIREMENT = "current.route30-saturated-headroom"
TEST = "population.route30.saturated-headroom"

MAP_ID = 34
TELEPORT = dict(map=MAP_ID, x=557, z=361, facing=0)
SAVED_MANKEY_PERSONALITY = 2920357538
# Six Wild actors, each at its own walkable pond-bank/path tile. On test3591 the
# native finalize rejects every prepared Rattata19 and Sentret161 request at
# every tile tried: they are grass-only species and the bank has no grass for a
# prepared startup. Pidgey16 replaces Rattata; Poliwag60, Hoothoot163 and
# Spinarak167 are accepted at these tiles. Natural refill still adds Rattata.
SPAWNS = (("pidgey-a", 16, 559, 364), ("pidgey-b", 16, 560, 366),
          ("poliwag-a", 60, 558, 365), ("poliwag-b", 60, 561, 363),
          ("hoothoot", 163, 559, 367), ("spinarak", 167, 560, 362))
SPAWN_LEVEL = 5

# A native spawn request fails with the first refusal while a natural spawn owns
# the queue, and with the second when natural spawn work takes the queued Entry
# before it adopts. Both leave the queue free. Natural destination scans on the
# pond bank keep the queue busy for many frames, so the runner answers either
# refusal with neutral frames and asks again; the refusal and every neutral
# frame stay in the retained stream and earn no credit.
BUSY_CODE = "busy"
BUSY_MESSAGE = "native spawn queue is already owned"
LOST_ENTRY_CODE = "spawn-rejected"
LOST_ENTRY_MESSAGE = "queued Entry ended without adopting an actor"
# The native finalize also refuses a request whose startup motion it cannot find;
# on test3591 that depends on game state (the same Pidgey tile was accepted and
# refused in different runs), so it is retried after neutral frames as well. A
# tile that never works is skipped after MAX_STARTUP_REFUSALS: prepared spawns
# only top the population up to the saturation the window then requires.
MAX_STARTUP_REFUSALS = 4
STARTUP_CODE = "spawn-rejected"
STARTUP_MESSAGE = "native profile/terrain/startup rejected this spawn"
# The saved Mankey may be mid-Hop when a request arrives; that is a transient
# refusal under the same code.
FOLLOWER_MOTION_MESSAGE = "follower/mount motion is active"
REFUSALS = ((BUSY_CODE, BUSY_MESSAGE), (BUSY_CODE, FOLLOWER_MOTION_MESSAGE),
            (LOST_ENTRY_CODE, LOST_ENTRY_MESSAGE), (STARTUP_CODE, STARTUP_MESSAGE))
# Natural refill may already have taken regular Wild slots, so six requests can
# need fewer than six prepared actors. Once the six regular slots are occupied
# the request is refused before any native work; that is the goal reached.
FULL_CODE = "population-full"
FULL_MESSAGE = "all six regular wild slots are occupied"
SPAWN_RETRY_FRAMES = 8
MAX_SPAWN_RETRIES = 40
# The refused request still runs native cycles before it returns, and the fresh
# snapshot reports the last completed queue, not that cycle. The neutral chunk
# that follows is rebased on its own first completion, bounded by this gap.
MAX_REFUSAL_CYCLES = 32

# Fixed input: UP then DOWN for 16 completed frames each, twenty-four times, with
# no run key, so the Player stays within about five tiles of the pond bank. A
# 120-frame step walked it 30 tiles north on test3591 and every Wild actor
# despawned by distance; 32-frame steps still reached 8 tiles north, and the
# Wild actors that wander south down the path despawned as well. A final neutral
# wait lets the Player finish its last tile.
WALK_FRAMES = 16
WALK_REPEATS = 24
SETTLE_FRAMES = 16
WINDOW_LOOPS = 2 * WALK_FRAMES * WALK_REPEATS
MINIMUM_CREDITED_LOOPS = 600
SETUP_SETTLE_FRAMES = 16

# Idle is the mandatory-wait return clock minus its entry clock (ARM9 scheduler
# ticks). Percentiles use the sorted samples at index len//100 and len//20.
# Route 30 pond bank (x=557,z=361), UP/DOWN steps, no run key (the old-ROM and
# first fixed-ROM figures used 120-frame steps; the test3588 run did too):
#   old-ROM diagnostic at 7 actors (before the TKT-0076 fix, 6 late loops of
#     955):                         min 14k, p1 150k, p5 231k, median 412k.
#   first diagnostic fixed ROM (7 actors, 716 loops, 0 late):
#                                   min 73k, p1 323k, p5 434k, median 672k.
#   accepted-mode run on the fixed ROM test3588 (720 credited loops, 0 late,
#     5-7 actors with natural distance despawn):
#                                   min 43k, p1 204k, p5 318k, median 483k.
# Floors sit between the old-ROM run and the accepted-mode fixed-ROM run, so
# the old behavior fails p1 and p5 (and its minimum is under the floor) while
# the fixed ROM passes every one. Test3590 then removed Move trips from the
# population (about 70k ticks per loop), which is why the floors were not
# lowered further.
MIN_WAIT_ARM9_TICKS = 30_000
P1_WAIT_ARM9_TICKS = 175_000
P5_WAIT_ARM9_TICKS = 275_000
# Saturation: the saved Mankey plus five Wild actors. The six regular Wild
# slots can all hold an actor (FULL_POPULATION_ACTORS = Mankey + six), but the
# fixed walk lets natural distance despawn briefly lower the count (the fixed
# ROM run showed 5 to 7), so ninety percent of credited loops must hold at
# least MIN_ACTIVE_ACTORS. The share with all seven is recorded, not required.
MIN_ACTIVE_ACTORS = 6
FULL_POPULATION_ACTORS = 7
MIN_SATURATED_PERCENT = 90
MIN_PLAYER_STEPS = 1

HANDLE_KEYS = ("slot", "generation", "fieldEpoch", "mapGeneration", "encounterGeneration")
SUBJECT = ("mankey", 56, "FOLLOWER", "existing")


def _spawn_id(name):
    return "spawn-" + name


SETUP = (
    ("route30-pond", "teleport", dict(TELEPORT)),
    ("pond-settle16", "step", dict(frames=SETUP_SETTLE_FRAMES, keys=[])),
    *((_spawn_id(name), "spawn", dict(species=species, form=0, role="wild",
                                      level=SPAWN_LEVEL, x=x, z=z))
      for name, species, x, z in SPAWNS),
    ("population-settle16", "step", dict(frames=SETUP_SETTLE_FRAMES, keys=[])),
    ("bind-mankey", "bind", dict(subject="mankey")),
    ("arm-window", "main-loop-pacing.arm", dict(maxFrames=WINDOW_LOOPS)),
)
ACTIONS = (
    *((f"{key.lower()}{WALK_FRAMES}-{index + 1:02d}", "step", dict(frames=WALK_FRAMES, keys=[key]))
      for index in range(WALK_REPEATS) for key in ("UP", "DOWN")),
    ("settle16", "step", dict(frames=SETTLE_FRAMES, keys=[])),
)
BUDGET = dict(maxFrames=9000, maxSeconds=1800, noProgressFrames=600,
              minObservedFrames=MINIMUM_CREDITED_LOOPS)
SPAWN_BUDGET = dict(maxSeconds=600, maxFrames=1200, noProgressFrames=1200)


def need(value, message):
    if not value:
        raise ValueError("Population headroom: " + message)


def _action_budget(action_id, op, args):
    if action_id == "route30-pond":
        return dict(maxSeconds=90, maxFrames=120, noProgressFrames=120)
    if op == "step":
        return dict(maxSeconds=90, maxFrames=args["frames"], noProgressFrames=args["frames"])
    if op == "spawn":
        return dict(SPAWN_BUDGET)
    return dict(maxSeconds=90, maxFrames=1, noProgressFrames=1)


def build_recipe():
    """The one reviewed recipe; the committed file must equal this value."""
    def actions(rows):
        return [dict(id=name, op=op, args=deepcopy(args), budget=_action_budget(name, op, args))
                for name, op, args in rows]
    return dict(
        schemaVersion=1, id=TEST,
        title="Route30 pond bank with a saturated population keeps loop headroom while walking",
        mode="prepared", fixture=dict(rom="test.nds", save="test.sav"),
        expectationSource="tests/overworld/scenarios/" + TEST + ".json",
        requirements=[REQUIREMENT], budgets=dict(BUDGET),
        subjects=[dict(id=SUBJECT[0], species=SUBJECT[1], role=SUBJECT[2], acquire=SUBJECT[3])],
        setup=actions(SETUP), actions=actions(ACTIONS),
        measurements=[dict(kind=KIND, subject="mankey")],
        assertions=[dict(kind="measurement-complete", measurement=KIND, when="final")])


def validate_recipe(test):
    need(test.get("id") == TEST and test.get("mode") == "prepared"
         and test.get("fixture") == dict(rom="test.nds", save="test.sav")
         and test.get("requirements") == [REQUIREMENT]
         and test.get("subjects") == [dict(id=SUBJECT[0], species=SUBJECT[1],
                                           role=SUBJECT[2], acquire=SUBJECT[3])]
         and test.get("measurements") == [dict(kind=KIND, subject="mankey")]
         and tuple((a["id"], a["op"], a["args"]) for a in test["setup"]) == SETUP
         and tuple((a["id"], a["op"], a["args"]) for a in test["actions"]) == ACTIONS
         and [a.get("budget") for a in test["setup"]] == [
             _action_budget(n, o, a) for n, o, a in SETUP]
         and [a.get("budget") for a in test["actions"]] == [
             _action_budget(n, o, a) for n, o, a in ACTIONS]
         and test.get("budgets") == BUDGET
         and test.get("assertions") == [dict(kind="measurement-complete",
                                             measurement=KIND, when="final")],
         "exact fixture, input or budget differs")


def refusal_of(error):
    """The exact (code, message) refusal an error carries, or None."""
    code = getattr(error, "code", None)
    return next(((c, m) for c, m in REFUSALS if code == c and m in str(error)), None)


def is_population_full(error):
    return getattr(error, "code", None) == FULL_CODE and FULL_MESSAGE in str(error)


def spawn_with_neutral_retry(spawn, on_refusal, neutral_frames, on_full=None, on_skip=None):
    """Ask for one prepared spawn; answer only the queue refusals with neutral frames.

    Any other failure, or more than MAX_SPAWN_RETRIES refusals, is raised as is.
    ``on_refusal(error)`` retains the refusal and ``neutral_frames()`` advances
    exactly SPAWN_RETRY_FRAMES completed frames; neither earns credit.
    """
    refusals = startup_refusals = 0
    while True:
        try:
            return spawn()
        except Exception as error:
            if on_full is not None and is_population_full(error):
                return on_full(error)
            if refusal_of(error) is None:
                raise
            if on_skip is not None and refusal_of(error) == (STARTUP_CODE, STARTUP_MESSAGE):
                startup_refusals += 1
                if startup_refusals > MAX_STARTUP_REFUSALS:
                    return on_skip(error)
            refusals += 1
            if refusals > MAX_SPAWN_RETRIES:
                raise
            on_refusal(error)
            neutral_frames()


def active_actor_count(sample):
    return sum(1 for actor in sample.get("actors", []) if actor.get("active") is True)


def _percentile_index(count, divisor):
    return count // divisor


def wait_summary(waits):
    """Minimum, 1st and 5th percentile of idle ticks, as in the measured runs."""
    ordered = sorted(waits)
    if not ordered:
        return dict(count=0, minimum=None, p1=None, p5=None, median=None, maximum=None)
    return dict(count=len(ordered), minimum=ordered[0],
                p1=ordered[_percentile_index(len(ordered), 100)],
                p5=ordered[_percentile_index(len(ordered), 20)],
                median=ordered[len(ordered) // 2], maximum=ordered[-1])


class PopulationHeadroomMeasurement:
    def __init__(self, test, source):
        validate_recipe(test)
        need(source.get("contractVersion") == 1 and set(source) == {
            "contractVersion", "romSha256", "sourceSaveSha256", "profileSha256"},
            "source identity differs")
        self.test, self.source = test, deepcopy(source)
        self.latest = None
        self.subjects = {}
        self.setup_index = self.action_index = self.action_frames = 0
        self.spawned = []
        self.skipped_full = 0
        self.skipped_startup = 0
        self.armed_active = 0
        self.rebase_next_chunk = False
        self.refusals = {}
        self.refusal_pending = None
        self.first = None
        self.armed_actors = set()
        self.seen_actors = set()
        self.pacing = []
        self.last_sequence = None
        self.last_player_pose = None
        self.last_player_tile = None
        self.moving_frames = self.player_steps = 0
        self.settled = None
        self.final_tile = None
        self.late_loops = self.render_stalls = 0
        self.maximum_arm9_ticks = self.maximum_native_cycles = self.maximum_frame_sequence = 0
        self.failures = []
        self.final_checked = False
        self.closed = False

    # -- boundaries -------------------------------------------------------
    def _boundary(self, sample):
        need(sample.get("fieldAvailable") is True
             and sample.get("observationBoundary") == "main-task-queue-completion"
             and sample.get("romSha256") == self.source["romSha256"]
             and sample.get("sourceSaveSha256") == self.source["sourceSaveSha256"]
             and sample.get("context", {}).get("mapId") == MAP_ID
             and sample.get("fieldControl", {}).get("taskPointer") == 0,
             "current Route30 field or source differs")
        native = sample.get("nativeObservation", {})
        need(native.get("coverageComplete") is True and native.get("installedBeforeBoot") is True
             and native.get("eventsDropped") == 0 and native.get("pendingUnframedEvents") == 0
             and native.get("profilesEvicted") == 0 and native.get("error") is None,
             "native reader lost data")
        need(not any(a.get("active") and a.get("role") == "MOUNTED" for a in sample.get("actors", [])),
             "player became mounted")
        party = [p for p in sample.get("party", []) if p.get("slot") == 2]
        need(len(party) == 1 and party[0].get("species") == 56
             and party[0].get("personality") == SAVED_MANKEY_PERSONALITY
             and party[0].get("identityVerified") is True,
             "saved Mankey party identity differs")

    def _actor(self, sample, name):
        bound = select_current_actor(sample, self.subjects[name])
        need(engine_binding_identity(bound["engineIdentity"])
             == engine_binding_identity(self.subjects[name]["engineIdentity"]),
             "full current engine identity changed")
        actor = next(a for a in sample["actors"] if a.get("handle") == bound["handle"])
        need(actor.get("species") == 56 and actor.get("role") == "FOLLOWER"
             and actor.get("subjectIdentity") == SAVED_MANKEY_PERSONALITY
             and actor.get("identityVerified") is True and actor.get("active") is True,
             "saved Mankey follower identity changed")
        return actor

    # -- prepared spawn ---------------------------------------------------
    def _populationFull(self, row):
        """The six regular Wild slots are already occupied: nothing left to prepare."""
        sample, receipt = row["snapshot"], row["receipt"]
        need(receipt.get("populationFull") is True and receipt.get("snapshot") == sample
             and (receipt.get("code"), receipt.get("message")) == (FULL_CODE, FULL_MESSAGE)
             and isinstance(receipt.get("events"), list)
             and active_actor_count(sample) >= FULL_POPULATION_ACTORS, "spawn lacks actual ADOPT")
        self.skipped_full += 1
        self.rebase_next_chunk = True

    def _startupSkipped(self, row):
        """Native finalize found no startup for this tile after bounded retries."""
        sample, receipt = row["snapshot"], row["receipt"]
        need(receipt.get("startupSkipped") is True and receipt.get("snapshot") == sample
             and (receipt.get("code"), receipt.get("message")) == (STARTUP_CODE, STARTUP_MESSAGE)
             and isinstance(receipt.get("events"), list), "spawn lacks actual ADOPT")
        self.skipped_startup += 1
        self.rebase_next_chunk = True

    def _adopt(self, name, species, row):
        sample, receipt = row["snapshot"], row["receipt"]
        value = receipt.get("value", {})
        observed = value.get("entrySpawn")
        if observed is None:
            # Immediate path: the runtime already waited for this exact actor.
            native = dict(slot=value.get("slot"))
            need(receipt.get("snapshot") == sample and value.get("species") == species
                 and type(value.get("slot")) is int and type(value.get("personality")) is int,
                 "spawn lacks actual ADOPT")
        else:
            entry = observed.get("receipt", {})
            native = entry.get("actor", {})
            need(receipt.get("snapshot") == sample and entry.get("version") == 1 and entry.get("size") == 64
                 and type(entry.get("serial")) is int and entry["serial"] > 0
                 and entry.get("status") == 1 and entry.get("queued") == 0 and native.get("reserved") == 0
                 and observed.get("frame") == sample["frame"] and value.get("species") == species
                 and native.get("slot") == value.get("slot"), "spawn lacks actual ADOPT")
        actors = [a for a in sample.get("actors", []) if a.get("species") == species
                  and a.get("role") == "WILD" and a.get("level") == SPAWN_LEVEL and a.get("form") == 0
                  and a.get("subjectIdentity") == value.get("personality")
                  and all(a.get("handle", {}).get(k) == native.get(k)
                          for k in (HANDLE_KEYS if observed is not None else ("slot",)))]
        need(len(actors) == 1, "ADOPT lacks one full current Actor")
        selected = select_current_actor(sample, actors[0])
        need(all(selected["handle"] != other["handle"] for other in self.spawned),
             "prepared actors share a handle")
        self.spawned.append(dict(name=name, species=species, handle=deepcopy(selected["handle"]),
                                 subjectIdentity=selected["subjectIdentity"],
                                 frame=sample["frame"]))

    def _refusal(self, name, row):
        """A busy refusal: exact code, retained events, a completed boundary."""
        receipt, sample = row.get("receipt", {}), row.get("snapshot", {})
        need((receipt.get("code"), receipt.get("message")) in REFUSALS
             and set(receipt) == {"code", "message", "events"} and isinstance(receipt.get("events"), list),
             "spawn refusal is not the busy native queue")
        self._boundary(sample)
        need(type(sample.get("frame")) is int and sample["frame"] >= self.latest["frame"],
             "spawn refusal boundary moved backwards")
        self.refusals[name] = self.refusals.get(name, 0) + 1
        need(self.refusals[name] <= MAX_SPAWN_RETRIES, "spawn stayed busy beyond its retry bound")
        need(self.refusal_pending is None, "spawn was refused twice without neutral frames")
        self.refusal_pending = name

    # -- raw events and the credited loop ---------------------------------
    def _events(self, events, end_frame, on_events=None, sample=None):
        need(isinstance(events, list) and len(events) <= 8192, "event prefix exceeds its bound")
        by_frame = {}
        for event in events:
            need(isinstance(event, dict) and type(event.get("frame")) is int
                 and 0 <= event["frame"] <= end_frame and isinstance(event.get("data"), dict),
                 "event is outside its actual completed boundary")
            by_frame.setdefault(event["frame"], []).append(event)
        if on_events is not None:
            for frame, rows in sorted(by_frame.items()):
                on_events(rows, frame)
        for event in events:
            data = event.get("data", {})
            if event.get("kind") == "trace-status":
                code = data.get("code")
                need(type(data.get("traceStream")) is int and data["traceStream"] > 0
                     and data.get("diagnosticOnly") is True
                     and data.get("coverageComplete") is not False
                     and code in ("window-started", "field-epoch-changed", "ring-overwrite", "window-ended"),
                     "semantic trace lost data or unknown notice")
                if code == "ring-overwrite":
                    need(type(data.get("count")) is int and data["count"] > 0
                         and type(data.get("unreadEventsLost")) is int and data["unreadEventsLost"] == 0,
                         "semantic trace lost data")
                elif code == "window-ended":
                    need(data.get("reason") == "stopped", "semantic trace expired before completion")
                elif code == "field-epoch-changed":
                    need(data.get("sequenceReset") is False, "semantic trace reset during field change")
            if event.get("kind") != "native-observation":
                continue
            sequence = data.get("sequence")
            need(type(sequence) is int and sequence > 0
                 and (self.last_sequence is None or sequence == self.last_sequence + 1),
                 "native receipt sequence gap")
            self.last_sequence = sequence
            if data.get("observation") == "stock-main-loop-pacing":
                self._pacing(data, event, end_frame, sample)

    def _pacing(self, data, event, end_frame, sample):
        after = data.get("afterQueueFrame")
        if self.first is None or type(after) is not int \
                or not self.first <= after < self.first + WINDOW_LOOPS:
            return
        need(sample is not None and sample.get("frame") == event.get("frame") == end_frame
             and data.get("flushedAtQueueFrame") == event.get("frame") == after + 1,
             "pacing row lacks its completed boundary")
        need(MainLoopProbe._clock_ok(data.get("guestClock"))
             and all(type(data.get(k)) is int and data[k] >= 0
                     for k in ("actorFrame", "nativeCycle", "frameCounter"))
             and data.get("returnSite") == RETURN_SITE and data.get("scope") == SCOPE
             and data.get("diagnosticOnly") is False and data.get("acceptedProof") is False
             and data.get("setupMode") == "prepared" and data.get("windowIndex") == 0
             and data.get("loopId") == len(self.pacing) + 1
             and after == self.first + len(self.pacing),
             "pacing owner or continuous credited window differs")
        interval = data.get("intervalFromPrevious")
        if self.pacing:
            need(isinstance(interval, dict)
                 and all(type(interval.get(k)) is int and interval[k] >= 0
                         for k in ("arm9Ticks", "nativeCycles", "frameSequence", "actorFrames")),
                 "pacing interval is missing")
        else:
            need(interval is None, "first pacing sample has an unbound interval")
        late = (data["frameCounter"] > NORMAL_MAIN_LOOP_NATIVE_CYCLES
                or (interval is not None
                    and (interval["nativeCycles"] > NORMAL_MAIN_LOOP_NATIVE_CYCLES
                         or interval["frameSequence"] > NORMAL_MAIN_LOOP_NATIVE_CYCLES
                         or interval["arm9Ticks"] > MAX_ZERO_STUTTER_ARM9_TICKS)))
        if late:
            self.late_loops += 1
        need(not late, "route observed an extra game frame")
        if interval is not None:
            need(interval == MainLoopProbe._interval(self.pacing[-1], data),
                 "pacing interval differs from its guest clocks")
            self.maximum_arm9_ticks = max(self.maximum_arm9_ticks, interval["arm9Ticks"])
            self.maximum_native_cycles = max(self.maximum_native_cycles, interval["nativeCycles"])
            self.maximum_frame_sequence = max(self.maximum_frame_sequence, interval["frameSequence"])
        wait = data.get("waitArm9Ticks")
        need(type(wait) is int and wait >= 0, "pacing row lacks waitArm9Ticks")
        need(data.get("waitEntrySite") == ENTRY_SITE and data.get("waitScope") == WAIT_SCOPE
             and type(data.get("waitEntryArm9Timestamp")) is int
             and data["guestClock"]["arm9Timestamp"] - data["waitEntryArm9Timestamp"] == wait,
             "wait envelope differs from its own entry and return clocks")
        need(wait <= (interval["arm9Ticks"] if interval is not None else MAX_ZERO_STUTTER_ARM9_TICKS),
             "wait envelope exceeds its own loop interval")
        # The per-loop floor is judged with the other floors once the whole window
        # is read, so a failed run still reports the complete idle distribution.
        self.pacing.append(dict(
            loopId=data["loopId"], afterQueueFrame=after, guestClock=deepcopy(data["guestClock"]),
            actorFrame=data["actorFrame"], nativeCycle=data["nativeCycle"],
            frameCounter=data["frameCounter"], waitArm9Ticks=wait,
            activeActors=active_actor_count(sample)))

    # -- Player input -----------------------------------------------------
    def _player_sample(self, sample):
        player = sample.get("player", {})
        need(all(type(player.get(k)) is int for k in ("x", "y", "x_prev", "y_prev", "pos_x", "pos_z")),
             "Player movement sample is missing")
        pose = [player["pos_x"], player["pos_z"]]
        if player["x"] != player["x_prev"] or player["y"] != player["y_prev"]:
            self.moving_frames += 1
            if pose == self.last_player_pose:
                self.render_stalls += 1
            need(pose != self.last_player_pose, "Player render froze during normal input")
        tile = (player["x"], player["y"])
        if self.last_player_tile is not None and tile != self.last_player_tile:
            self.player_steps += 1
        self.last_player_tile = tile
        self.last_player_pose = pose
        self.settled = (tile == (player["x_prev"], player["y_prev"]))

    def _window_sample(self, sample):
        """Population identity of one observed frame; informational for creation."""
        if self.first is None:
            return
        keys = {self._actor_key(a) for a in sample.get("actors", [])
                if a.get("active") is True and a.get("role") == "WILD"}
        self.seen_actors |= keys

    @staticmethod
    def _actor_key(actor):
        handle = actor.get("handle", {})
        return (actor.get("subjectIdentity"), actor.get("species"),
                *(handle.get(k) for k in HANDLE_KEYS))

    # -- records ----------------------------------------------------------
    def _after_refusal(self, row):
        """Previous boundary for the neutral chunk after a refusal.

        Frames must continue exactly. Only the native-cycle origin is rebased:
        it is the first completing interval's cycle, which must not move
        backwards and must stay within MAX_REFUSAL_CYCLES of the snapshot.
        """
        intervals, samples = row.get("cycleIntervals"), row.get("samples")
        need(isinstance(intervals, list) and isinstance(samples, list) and samples
             and samples[0].get("frame") == self.latest["frame"] + 1,
             "spawn retry neutral frames do not continue the refusal boundary")
        index = next((i for i, interval in enumerate(intervals, 1)
                      if type(interval.get("completedGameFrame")) is int
                      and interval["completedGameFrame"] > self.latest["frame"]), None)
        need(index is not None and type(samples[0].get("nativeCycle")) is int,
             "spawn retry neutral frames lack a completed queue")
        origin = samples[0]["nativeCycle"] - index
        need(self.latest["nativeCycle"] <= origin <= self.latest["nativeCycle"] + MAX_REFUSAL_CYCLES,
             "spawn retry native clock is outside the refusal gap")
        return dict(self.latest, nativeCycle=origin)

    def _chunk(self, row, phase, args, on_sample, on_events, previous=None):
        """Validate and observe one raw completed-input chunk."""
        for sample, events, _ in validate_raw_chunk(row, self.latest if previous is None else previous):
            self._boundary(sample)
            for subject in self.subjects:
                self._actor(sample, subject)
            self._events(events, sample["frame"], on_events, sample)
            # Setup waits keep coverage but earn no movement or pacing credit.
            if phase == "observe":
                self._player_sample(sample)
                self._window_sample(sample)
            self.latest = deepcopy(sample)
            self.action_frames += 1
            if on_sample:
                on_sample(sample, len(self.pacing))
        need(self.action_frames <= args["frames"], "input frame bound exceeded")

    def observe_record(self, row, on_sample=None, on_events=None):
        try:
            if "initialSnapshot" in row:
                need(self.latest is None and row.get("phase") == "setup", "initial boundary is misplaced")
                sample = row["initialSnapshot"]
                need(sample.get("romSha256") == self.source["romSha256"]
                     and sample.get("sourceSaveSha256") == self.source["sourceSaveSha256"],
                     "source ROM/save differs")
                initial = row.get("initialEvents", [])
                start = row.get("initialEventStartFrame", sample["frame"])
                need(type(start) is int and 0 <= start <= sample["frame"]
                     and all(e.get("kind") == "native-observation" or start <= e.get("frame", -1)
                             for e in initial), "initial semantic prefix is outside record start")
                self._events(initial, sample["frame"], on_events)
                self.latest = deepcopy(sample)
                return self.result()
            phase = row.get("phase")
            need(phase in ("setup", "observe") and (phase == "setup" or self.setup_index == len(SETUP)),
                 "action phase is misplaced")
            expected = SETUP if phase == "setup" else ACTIONS
            index = self.setup_index if phase == "setup" else self.action_index
            need(index < len(expected) and row.get("action") == expected[index][0], "action order differs")
            name, op, args = expected[index]
            if op == "spawn" and row.get("command") is None:
                # Neutral frames answer one busy refusal, then the same spawn is asked again.
                need(self.refusal_pending == name and "command" not in row
                     and row.get("requestedInput") == dict(
                         frames=SPAWN_RETRY_FRAMES, keys=[], releaseAtEnd=False, diagnosticDetails=False),
                     "spawn retry lacks its busy refusal and exact neutral frames")
                self.action_frames = 0
                self._chunk(row, "setup", dict(frames=SPAWN_RETRY_FRAMES), on_sample, on_events,
                            self._after_refusal(row))
                need(self.action_frames == SPAWN_RETRY_FRAMES, "spawn retry neutral frames are incomplete")
                self.action_frames = 0
                self.refusal_pending = None
                return self.result()
            if op == "step":
                need("command" not in row, "normal input became a command")
                need(row.get("requestedInput") == dict(frames=row.get("completedGameFrames"), keys=args["keys"],
                                                       releaseAtEnd=False, diagnosticDetails=False),
                     "actual normal input keys or count changed")
                previous = self._after_refusal(row) if self.rebase_next_chunk else None
                self.rebase_next_chunk = False
                self._chunk(row, phase, args, on_sample, on_events, previous)
                if self.action_frames < args["frames"]:
                    return self.result()
                if name == "settle16":
                    self.final_tile = (self.latest["player"]["x"], self.latest["player"]["y"])
                self.action_frames = 0
            else:
                if op == "spawn" and row.get("command") == "spawn-refused":
                    self._refusal(name, row)
                    self._events(row["receipt"]["events"], row["snapshot"]["frame"], on_events)
                    self.latest = deepcopy(row["snapshot"])
                    return self.result()
                need(row.get("command") == op, "native command differs")
                need(self.refusal_pending is None, "spawn retry neutral frames are missing")
                sample, receipt = row["snapshot"], row.get("receipt", {})
                self._boundary(sample)
                self._events(receipt.get("events", []), sample["frame"], on_events)
                if op == "teleport":
                    need((sample["player"].get("x"), sample["player"].get("y"))
                         == (TELEPORT["x"], TELEPORT["z"]), "teleport did not reach the pond bank")
                elif op == "spawn":
                    species = next(s for n, s, _, _ in SPAWNS if _spawn_id(n) == name)
                    if receipt.get("populationFull") is True:
                        self._populationFull(row)
                    elif receipt.get("startupSkipped") is True:
                        self._startupSkipped(row)
                    else:
                        self._adopt(name.removeprefix("spawn-"), species, row)
                elif op == "bind":
                    actors = [a for a in sample["actors"] if a.get("species") == 56
                              and a.get("role") == "FOLLOWER" and a.get("active") is True
                              and a.get("subjectIdentity") == SAVED_MANKEY_PERSONALITY]
                    need(len(actors) == 1, "saved Mankey follower is missing")
                    self.subjects["mankey"] = select_current_actor(sample, actors[0])
                    need(receipt == select_current_actor(sample, self.subjects["mankey"]),
                         "bound full Actor differs")
                elif op == "main-loop-pacing.arm":
                    need(set(self.subjects) == {"mankey"}
                         and len(self.spawned) + self.skipped_full + self.skipped_startup == len(SPAWNS),
                         "six Wild actors and the saved Mankey are not admitted")
                    self._actor(sample, "mankey")
                    probe = receipt.get("probe", {})
                    need(sample["frame"] == self.latest["frame"]
                         and probe.get("armedAtQueueFrame") == sample["frame"]
                         and probe.get("firstObservedQueueFrame") == sample["frame"] + 1
                         and probe.get("guestMemoryWrites") == 0, "pacing arm differs")
                    need(type(probe.get("lastObservedQueueFrame")) is int
                         and probe["lastObservedQueueFrame"] - probe["firstObservedQueueFrame"]
                         >= MINIMUM_CREDITED_LOOPS,
                         "armed pacing window is shorter than the required credited loops")
                    need(probe["lastObservedQueueFrame"] == probe["firstObservedQueueFrame"] + WINDOW_LOOPS,
                         "armed pacing window differs from the declared walk")
                    need(active_actor_count(sample) >= MIN_ACTIVE_ACTORS,
                         "population is not saturated when the window arms")
                    self.first = probe["firstObservedQueueFrame"]
                    self.armed_active = active_actor_count(sample)
                    self.last_player_tile = (sample["player"]["x"], sample["player"]["y"])
                    self.last_player_pose = [sample["player"]["pos_x"], sample["player"]["pos_z"]]
                    self.armed_actors = {self._actor_key(a) for a in sample["actors"]
                                         if a.get("active") is True and a.get("role") == "WILD"}
                    self.seen_actors = set(self.armed_actors)
                self.latest = deepcopy(sample)
            if phase == "setup":
                self.setup_index += 1
            else:
                self.action_index += 1
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    # -- verdict ----------------------------------------------------------
    def _final_checks(self):
        need(self.setup_index == len(SETUP) and self.action_index == len(ACTIONS),
             "walk ended before its complete exact input script")
        credited = len(self.pacing)
        need(credited >= MINIMUM_CREDITED_LOOPS, "fewer than the required credited loops")
        need(credited == WINDOW_LOOPS, "credited window is incomplete")
        summary = wait_summary([row["waitArm9Ticks"] for row in self.pacing])
        need(summary["minimum"] >= MIN_WAIT_ARM9_TICKS, "idle headroom below its per-loop floor")
        need(summary["p1"] >= P1_WAIT_ARM9_TICKS, "idle headroom 1st percentile is below its floor")
        need(summary["p5"] >= P5_WAIT_ARM9_TICKS, "idle headroom 5th percentile is below its floor")
        saturated = sum(1 for row in self.pacing if row["activeActors"] >= MIN_ACTIVE_ACTORS)
        need(saturated * 100 >= credited * MIN_SATURATED_PERCENT,
             "fewer than six active actors in more than ten percent of credited loops")
        need(self.player_steps >= MIN_PLAYER_STEPS, "window contains no Player step")
        need(self.settled is True and self.latest.get("context", {}).get("mapId") == MAP_ID,
             "Player did not end on a settled Route30 tile")

    def finish(self):
        if not self.closed:
            if not self.failures:
                try:
                    self._final_checks()
                    self.final_checked = True
                except (ValueError, KeyError, TypeError) as error:
                    self.failures.append(str(error))
            self.closed = True
        return self.result()

    close = finish

    @property
    def ready(self):
        return self.closed and self.final_checked and not self.failures

    def result(self):
        credited = len(self.pacing)
        saturated = sum(1 for row in self.pacing if row["activeActors"] >= MIN_ACTIVE_ACTORS)
        counts = [row["activeActors"] for row in self.pacing]
        return dict(
            kind=KIND, passed=self.ready, ready=self.ready, closed=self.closed, acceptedProof=False,
            source=deepcopy(self.source), requirements=[REQUIREMENT], failures=list(self.failures),
            observedFrames=credited, observedFrameUnit="completed-main-loop-return",
            subjects=deepcopy(self.subjects),
            timingWindow=[self.first, self.first + WINDOW_LOOPS] if self.first is not None else None,
            pacing=dict(
                sampleCount=credited, intervalCount=max(0, credited - 1),
                maximumArm9Ticks=self.maximum_arm9_ticks, maximumNativeCycles=self.maximum_native_cycles,
                maximumFrameSequence=self.maximum_frame_sequence,
                maximumZeroStutterArm9Ticks=MAX_ZERO_STUTTER_ARM9_TICKS,
                normalMaximumNativeCycles=NORMAL_MAIN_LOOP_NATIVE_CYCLES,
                lateMainLoopCount=self.late_loops, renderStallCount=self.render_stalls),
            headroom=dict(wait_summary([row["waitArm9Ticks"] for row in self.pacing]),
                          waitSampleCount=credited,
                          floors=dict(minimum=MIN_WAIT_ARM9_TICKS, p1=P1_WAIT_ARM9_TICKS,
                                      p5=P5_WAIT_ARM9_TICKS),
                          samples=[row["waitArm9Ticks"] for row in self.pacing]),
            population=dict(
                minimumActiveActors=min(counts, default=0), maximumActiveActors=max(counts, default=0),
                requiredActiveActors=MIN_ACTIVE_ACTORS, saturatedLoops=saturated,
                saturatedPercent=(saturated * 100 // credited if credited else 0),
                requiredSaturatedPercent=MIN_SATURATED_PERCENT,
                # Informational only: loops with all seven actors present.
                sevenActorLoops=sum(1 for row in self.pacing
                                    if row["activeActors"] >= FULL_POPULATION_ACTORS),
                sevenActorPercent=(sum(1 for row in self.pacing
                                       if row["activeActors"] >= FULL_POPULATION_ACTORS)
                                   * 100 // credited if credited else 0),
                spawned=deepcopy(self.spawned), spawnRetries=sum(self.refusals.values()),
                preparedRequests=len(SPAWNS), alreadyFullRequests=self.skipped_full, startupSkippedRequests=self.skipped_startup,
                armedActiveActors=self.armed_active,
                # Informational only: the population is already saturated.
                naturalCreations=len(self.seen_actors - self.armed_actors)),
            player=dict(steps=self.player_steps, movingFrames=self.moving_frames,
                        settled=self.settled, finalTile=list(self.final_tile or ())))
