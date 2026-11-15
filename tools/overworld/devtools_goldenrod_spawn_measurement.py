"""Natural Goldenrod births through the unchanged spawn and height readers.

Expected sites come from T79's declared views/topology, never the run. Player
teleports are prepared setup; species, profiles, RNG and population stay normal.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from tools.overworld.devtools_movement_predicates import check_movement_predicate, player_settled_at
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor, validate_field_absence
from tools.overworld.devtools_spawn_outcome_records import need, parse_record, quality
from tools.overworld.devtools_spawn_priority_measurement import SELECTED, SpawnPriorityMeasurement, _record
from tools.overworld.devtools_spawn_surface_measurement import (
    LAND_BEHAVIORS, _check_natural_appear_hop_surface, check_natural_raised_surface)

BEHIND = "goldenrod-natural-behind-v1"
RAISED = "goldenrod-natural-raised-v1"
UNDERGROUND = "goldenrod-natural-underground-v1"
KINDS = frozenset((BEHIND, RAISED, UNDERGROUND))
FRAMES, SEGMENT, MAX_FRAMES = 900, 150, 1085
BEHIND_TILES = frozenset(((374, 359), (375, 359), *((x, 332) for x in range(375, 379))))
# Main public corridor only. The independent offline map footprint is filled
# from the authored native room survey, not from whichever births occur.
# Independent embedded land511 floor mesh survey: horizontal chikayuka_a/b
# faces, tile-centre projection, then native collision/Land filtering. These
# 250 cells include the three ordinary floor words; 0x0000 padding is excluded.
_UNDERGROUND_ROWS = {
    3: ((4,9),), 4: ((4,10),(20,20)), 5: ((4,10),(17,20)),
    6: ((4,10),(15,20),(22,22)), 7: ((4,20),(22,22)), 8: ((4,20),(22,22)),
    9: ((4,17),(19,20),(22,22)), 10: ((4,20),(22,22)), 11: ((4,20),(22,22)),
    12: ((5,10),), 13: ((5,10),), 14: ((5,9),), 15: ((5,8),),
    16: ((5,8),(10,10)), 17: ((5,8),(10,10)), 18: ((4,8),), 19: ((4,8),),
    20: ((4,8),(10,10)), 21: ((4,8),(10,10)), 22: ((5,8),(10,10)),
    23: ((5,8),), 24: ((5,9),), 25: ((5,9),), 26: ((5,8),),
    27: ((5,8),(10,10)), 28: ((4,8),(10,10)), 29: ((4,8),),
    30: ((4,9),(25,25)), 31: ((4,26),),
}
UNDERGROUND_FLOOR = {(x,y): 0x0600 for y,ranges in _UNDERGROUND_ROWS.items()
                     for low,high in ranges for x in range(low,high+1)}
UNDERGROUND_FLOOR.update({(4,3):0x065F,(4,4):0x065F,(4,5):0x065F,(20,4):0x066E,(25,30):0x066E})
CASES = {
    BEHIND: dict(test="population.goldenrod-behind-buildings", requirement="current.goldenrod-natural-behind", start=(76, 368, 366)),
    RAISED: dict(test="population.goldenrod-raised-birds", requirement="current.goldenrod-natural-raised", start=(76, 346, 351)),
    UNDERGROUND: dict(test="population.goldenrod-underground", requirement="current.goldenrod-natural-underground", start=(199, 6, 19)),
}
MASKS = {52: 0x801, 19: 0x801, 568: 0x801, 88: 0x801, 479: 0x801,
         209: 1, 519: 65, 198: 68}
ROOF_WINDOW = json.loads((Path(__file__).resolve().parent / "fixtures/goldenrod_roof_window.json").read_text())
ROOF_HEIGHTS = {tuple(row["tile"]): row["heightFx32"] for row in ROOF_WINDOW["roofPoints"]}


def check_roof_window(catalog):
    """Bind the fixed natural view to its independent native roof/Canopy oracle."""
    need(ROOF_WINDOW["center"] == [346,351] and ROOF_WINDOW["nativeWord"] == 0x0600
         and len(ROOF_HEIGHTS) == ROOF_WINDOW["roof"] == 107 and ROOF_WINDOW["canopy"] == 0,
         "Goldenrod independent roof window differs")
    lands = {tuple(cell["block"]):cell["land"] for cell in ROOF_WINDOW["loadedCells"]}
    roofs, canopies = {}, set()
    for y in range(343,360):
        for x in range(338,355):
            if max(abs(x-346),abs(y-351)) < 4:
                continue
            land = lands.get((x//32,y//32))
            need(land is not None, "Goldenrod roof window leaves its native loaded scope")
            for row in catalog["instances"]:
                if row["land_data_id"] != land or not (row["min_x"] <= x%32 < row["min_x"]+row["width"]
                        and row["min_y"] <= y%32 < row["min_y"]+row["height"]):
                    continue
                if row["surface_type"] == "rooftop":
                    need((x,y) not in roofs or roofs[(x,y)] == row["height_fx32"], "Goldenrod roof heights overlap")
                    roofs[(x,y)] = row["height_fx32"]
                elif row["surface_type"] == "canopy":
                    canopies.add((x,y))
    need(roofs == ROOF_HEIGHTS and not canopies,
         "Goldenrod current catalog differs from the independent 107-Roof/zero-Canopy window")


def setup_for(kind):
    m, x, z = CASES[kind]["start"]
    return (("natural-window", "teleport", dict(map=m, x=x, z=z, facing=1)),
            ("warp-settle", "step", dict(frames=24, keys=[])),
            ("current-follower", "wait", dict(predicate=dict(kind="follower-settled", species=56, partySlot=2, when="final"))),
            ("bind-current-field", "bind", dict(subject="mankey")))


def actions_for(kind):
    return tuple((f"natural-{i + 1}", "step", dict(frames=SEGMENT, keys=[])) for i in range(FRAMES // SEGMENT))


def validate_recipe(test):
    kind = test.get("measurements", [{}])[0].get("kind")
    need(kind in KINDS, "Goldenrod natural recipe kind differs")
    case = CASES[kind]
    need(test.get("id") == case["test"] and test.get("mode") == "prepared"
         and test.get("fixture") == dict(rom="test.nds", save="test.sav")
         and test.get("requirements") == [case["requirement"]]
         and test.get("subjects") == [dict(id="mankey", species=56, role="FOLLOWER", acquire="existing")]
         and test.get("measurements") == [dict(kind=kind, subject="mankey")]
         and tuple((a["id"], a["op"], a["args"]) for a in test["setup"]) == setup_for(kind)
         and tuple((a["id"], a["op"], a["args"]) for a in test["actions"]) == actions_for(kind)
         and test.get("assertions") == [dict(kind="measurement-complete", measurement=kind, when="final")]
         and test.get("budgets") == dict(maxSeconds=480, maxFrames=MAX_FRAMES,
                                        noProgressFrames=180, minObservedFrames=FRAMES),
         "Goldenrod natural recipe changed its declared setup or neutral window")
    need([a["budget"] for a in test["setup"]] == [
        dict(maxSeconds=90, maxFrames=120, noProgressFrames=120),
        dict(maxSeconds=30, maxFrames=24, noProgressFrames=24),
        dict(maxSeconds=90, maxFrames=64, noProgressFrames=64),
        dict(maxSeconds=10, maxFrames=1, noProgressFrames=1)]
        and all(a["budget"] == dict(maxSeconds=90, maxFrames=SEGMENT, noProgressFrames=SEGMENT)
                for a in test["actions"]), "Goldenrod natural action budgets differ")


def source_inputs(root):
    catalog_bytes = (root / "data/generated/overworld_wild_roof_catalog.json").read_bytes()
    catalog = json.loads(catalog_bytes)
    check_roof_window(catalog)
    # This is a source-time check of independently named expected tiles. It
    # does not learn locations from native births or grant tile legality.
    topology = []
    for x, y in sorted(BEHIND_TILES):
        for row in catalog["instances"]:
            if row["surface_type"] == "rooftop" and row["min_x"] <= x % 32 < row["min_x"] + row["width"] \
                    and row["min_y"] <= (y + 1) % 32 < row["min_y"] + row["height"]:
                topology.append(dict(target=[x, y], landDataId=row["land_data_id"],
                    roofLocal=[x % 32, (y + 1) % 32], roofSource=row["source"]))
    need({tuple(r["target"]) for r in topology} == BEHIND_TILES,
         "Goldenrod declared Behind topology is absent from the current catalog")
    return dict(contractVersion=1,
        profileSha256=hashlib.sha256((root / "data/overworld_behavior_profiles.json").read_bytes()).hexdigest(),
        catalogSha256=hashlib.sha256(catalog_bytes).hexdigest(), behindTopology=topology)


def resolved_placement(spawn, source, attempt, events):
    final = spawn["finalization"]["receipt"]
    world, encounter = spawn["worldContext"], spawn["preparedEncounter"]
    finals = [event["data"] for event in events if event.get("kind") == "native-observation"
              and event.get("data", {}).get("observation") == "spawn-finalized"
              and event["data"].get("spawnAttemptId") == attempt["spawnAttemptId"]
              and event["data"].get("worldContext") == world]
    need(finals and finals[-1] == final
         and all(b["sequence"] > a["sequence"] and b["finalizationId"] > a["finalizationId"]
                 for a, b in zip(finals, finals[1:])),
         "Goldenrod natural attempt lacks its exact ordered finalizers")
    for item in finals:
        need(item.get("nativeOwner") == "Query.NativeFinalize"
             and item.get("worldContext") == item.get("returnWorldContext") == world
             and item.get("fieldPointer") == world.get("fieldPointer")
             and item.get("statePointer") == world.get("statePointer")
             and all(item.get(key) == final.get(key) for key in
                     ("preparedPointer", "slot", "terrain", "querySerial", "spawnAttemptId"))
             and item.get("inputEncounter") == encounter,
             "Goldenrod natural attempt owner differs from its constructor")
        need(isinstance(item.get("resolverReceipts"), list) and len(item["resolverReceipts"]) <= 1,
             "Goldenrod natural attempt lacks its single initial profile preparation")
    preparations = [(item, receipt) for item in finals for receipt in item["resolverReceipts"]]
    need(len(preparations) == 1 and preparations[0][0] is finals[0],
         "Goldenrod natural attempt lacks its single initial profile preparation")
    prepared_final, receipt = preparations[0]
    request = bytes.fromhex(receipt.get("requestHex", ""))
    result = bytes.fromhex(receipt.get("resultHex", ""))
    map_id = world["mapId"]
    expected = 1 if map_id == 199 else MASKS.get(encounter["species"])
    need(expected is not None and receipt.get("resolved") is True
         and receipt.get("sourceSha256") == source["profileSha256"]
         and receipt.get("finalizationId") == prepared_final["finalizationId"]
         and receipt.get("inputEncounter") == encounter
         and len(request) == 44 and len(result) == 216
         and int.from_bytes(request[0:2], "little") == encounter["species"]
         and int.from_bytes(request[2:4], "little") == map_id
         and request[8] == encounter["level"] and request[9] == 0
         and request[12:20] == bytes(8)
         and int.from_bytes(result[52:54], "little") == expected
         and int.from_bytes(result[54:56], "little") == 0xBFF,
         "Goldenrod native placement mask/map differs from its authored application")
    runtime = finals[0].get("queueAfter", {}).get("runtime")
    pointer = spawn.get("preparedPointer")
    need(type(pointer) is int and 0x02000000 <= pointer <= 0x02400000 - 260 and pointer % 4 == 0
         and type(final.get("querySerial")) is int and final["querySerial"] > 0,
         "Goldenrod natural attempt owner differs from its constructor")
    rolled = (encounter["personality"].to_bytes(4, "little") + encounter["species"].to_bytes(2, "little")
              + bytes((encounter["form"], encounter["level"])))
    for item in finals:
        cache = item.get("queueAfter", {})
        raw = bytes.fromhex(cache.get("preparedHex", ""))
        # OverworldWildPreparedSpawn: encounter12, behaviorResolution36,
        # sizeof260. NativeWildPreparedSpawnAbiTests seals the ARM layout.
        need(type(runtime) is int and runtime > 0 and cache.get("runtime") == runtime
             and cache.get("preparedPointer") == spawn.get("preparedPointer") == item.get("preparedPointer")
             and cache.get("serial") == item.get("querySerial")
             and cache.get("terrain") == item.get("terrain")
             and len(raw) == 260 and raw[12:20] == rolled and raw[36:252] == result,
             "Goldenrod natural cached profile differs from its one preparation")
    return expected


def witnesses(kind, report, snapshots, events, source, *, setup_finalizers=()):
    constructors = {e["data"]["sequence"]: e["data"] for e in events
                    if e.get("data", {}).get("observation") == "spawn-prepared"}
    found, observed = [], []
    for attempt in report["naturalAttempts"]:
        for creation in attempt["creations"]:
            spawn = constructors[creation["sequence"]]
            need(spawn["worldContext"]["mapId"] == CASES[kind]["start"][0] and spawn.get("terrain") == 0,
                 "Goldenrod natural birth uses the wrong map or encounter terrain")
            mask = resolved_placement(spawn, source, attempt, [*setup_finalizers, *events])
            target = tuple(spawn["position"])
            cell = spawn.get("initialLandingHeight", {}).get("loadedTerrain", {}).get("cell", {})
            species = creation["species"]
            observed.append(dict(species=species, target=list(target), mask=mask, handle=deepcopy(creation["handle"])))
            if kind == UNDERGROUND:
                need(species in (19, 88) and target in UNDERGROUND_FLOOR
                     and cell.get("attribute") == UNDERGROUND_FLOOR.get(target) and cell.get("collision") is False,
                     "Underground natural birth is outside the declared public corridor floor")
            if mask & 0x800:
                need(target in BEHIND_TILES and any(r["target"] == list(target)
                     and r["landDataId"] == cell.get("provenance", {}).get("landDataId")
                     for r in source["behindTopology"]),
                     "Behind birth is outside the independently declared north-of-roof topology")
            hit = spawn.get("initialLandingHeight", {}).get("surfaceQuery", {}).get("hit")
            eligible = (mask == 0x801 if kind == BEHIND else species in (19, 88)
                        if kind == UNDERGROUND else species in (519, 198) and isinstance(hit, dict)
                        and hit.get("surfaceType") == 0)
            if not eligible or not creation["insideSnapshotWindow"]:
                continue
            if kind == RAISED:
                need(target in ROOF_HEIGHTS and hit.get("height") == ROOF_HEIGHTS[target],
                     "Goldenrod bird birth is outside the independent native roof tile/height window")
            for snapshot in snapshots:
                if snapshot["frame"] <= creation["frame"]:
                    continue
                actors = [a for a in snapshot.get("actors", []) if a.get("handle") == creation["handle"]]
                if len(actors) != 1:
                    continue
                actor = actors[0]
                if actor.get("controllerState") != 0 or actor.get("motionPhase") != "IDLE" \
                        or actor.get("engineObject", {}).get("movement_cmd") != 255:
                    continue
                pose = actor["engineObject"]
                if [pose.get("x"), pose.get("y")] != list(target) or [pose.get("pos_x"), pose.get("pos_z")] \
                        != [(coordinate << 16) + 0x8000 for coordinate in target]:
                    continue
                if kind == RAISED:
                    landing = check_natural_raised_surface(spawn, snapshot, species=species, surface_type=hit["surfaceType"])
                else:
                    landing = _check_natural_appear_hop_surface(spawn, snapshot, species=species, terrain=0, prepared=True,
                        land_behaviors=LAND_BEHAVIORS | {0, 0x5F, 0x6E})
                found.append(dict(spawnAttemptId=attempt["spawnAttemptId"], constructorSequence=creation["sequence"],
                    constructorFrame=creation["frame"], handle=deepcopy(creation["handle"]), mapId=spawn["worldContext"]["mapId"],
                    species=species, mask=mask, target=list(target), landing=landing))
                break
    need(found, "no required natural Goldenrod birth and same-handle completed landing were observed")
    return dict(landings=found, births=observed, coverage=report["quality"])


class GoldenrodSpawnMeasurement:
    def __init__(self, test, source):
        validate_recipe(test)
        need(isinstance(source, dict) and set(source) == {"contractVersion", "profileSha256", "catalogSha256", "behindTopology"}
             and source["contractVersion"] == 1 and all(isinstance(source[k], str) and len(source[k]) == 64
             for k in ("profileSha256", "catalogSha256")) and isinstance(source["behindTopology"], list),
             "Goldenrod natural source identity differs")
        self.test, self.kind, self.source = test, test["measurements"][0]["kind"], source
        self.latest = self.subject = self.follower_identity = None
        self.setup_index = self.action_index = self.action_frames = self.observed_frames = 0
        self.snapshots, self.events, self.failures = [], [], []
        self.setup_finalizers = []
        self.last_sequence, self.outcomes, self.closed = None, {}, False

    def _setup_events(self, sample, events):
        quality(_record([sample], events))
        for event in events:
            if event.get("kind") != "native-observation": continue
            need(type(self.last_sequence) is int,
                 "Goldenrod setup native receipt lacks its drained command watermark")
            SpawnPriorityMeasurement._event_coverage(self, event)
            data = event["data"]
            if data.get("observation") != "spawn-finalized": continue
            world = data.get("worldContext", {})
            need(sample.get("fieldAvailable") is True and data.get("returnWorldContext") == world
                 and all(world.get(k) == sample.get("context", {}).get(k)
                         for k in ("mapId", "fieldEpoch", "mapGeneration"))
                 and world.get("fieldPointer") == sample.get("fieldControl", {}).get("fieldPointer"),
                 "Goldenrod setup finalizer differs from its native field boundary")
            self.setup_finalizers.append(deepcopy(event))
            need(len(self.setup_finalizers) <= MAX_FRAMES, "Goldenrod setup finalizers exceed their bound")

    def _boundary(self, sample, *, transient=False):
        quality(_record([sample], []))
        if transient and sample.get("fieldAvailable") is False:
            validate_field_absence(sample)
            return
        need(sample.get("fieldAvailable") is True and (transient
             or sample.get("fieldControl", {}).get("taskPointer") == 0),
             "Goldenrod natural field boundary differs")
        party = [p for p in sample.get("party", []) if p.get("slot") == 2]
        need(len(party) == 1 and party[0].get("species") == 56 and party[0].get("identityVerified") is True
             and party[0].get("isEgg") is False and party[0].get("hp", 0) > 0,
             "Goldenrod natural setup lacks the saved party-slot2 Mankey")
        if self.follower_identity is None:
            self.follower_identity = party[0]["personality"]
        need(party[0]["personality"] == self.follower_identity, "Goldenrod natural setup changed the saved follower")

    def _ready(self, action):
        return action["op"] == "wait" and check_movement_predicate(action["args"]["predicate"], self.latest)

    def _pose(self, sample):
        m, x, z = CASES[self.kind]["start"]
        need(sample["context"]["mapId"] == m and [sample["player"][k] for k in ("x", "y")] == [x, z]
             and all(sample.get("selector", {}).get(k) == 0 for k in ("heldKeys", "newKeys", "physicalPressed", "simulatedKeys")),
             "Goldenrod natural window changed its declared map, player or neutral input")

    def observe_record(self, row, on_sample=None):
        try:
            if "initialSnapshot" in row:
                need(self.latest is None and row.get("phase") == "setup", "Goldenrod initial boundary differs")
                self.latest = deepcopy(row["initialSnapshot"])
                self._boundary(self.latest)
                return self.result()
            setup = row.get("phase") == "setup"
            actions = self.test["setup"] if setup else self.test["actions"]
            if setup:
                while self.setup_index < len(actions) and actions[self.setup_index]["id"] != row.get("action"):
                    need(self._ready(actions[self.setup_index]), "Goldenrod setup skipped its unsettled follower")
                    self.setup_index += 1
            else:
                need(self.setup_index == len(self.test["setup"]) and row.get("phase") == "observe",
                     "Goldenrod observation began before setup")
            index = self.setup_index if setup else self.action_index
            need(index < len(actions) and row.get("action") == actions[index]["id"], "Goldenrod natural action order differs")
            action = actions[index]
            if "samples" not in row:
                need(setup and row.get("command") == action["op"] and action["op"] in ("bind", "teleport"),
                     "Goldenrod natural setup command differs")
                sample = row["snapshot"]
                if action["op"] == "teleport":
                    self._boundary(sample, transient=True)
                    receipt = row["receipt"]
                    need(receipt.get("preparedOnly") is True and all(receipt["snapshot"].get(k) == sample.get(k)
                         for k in ("frame", "nativeCycle", "context"))
                         and receipt.get("setupBoundary", {}).get("eventsDrained") is True
                         and all(receipt["setupBoundary"].get(k) == sample.get(k) for k in ("frame", "nativeCycle")),
                         "Goldenrod setup warp lacks its native completed receipt")
                    self.last_sequence = sample.get("nativeObservation", {}).get("sequence")
                else:
                    self._boundary(sample); self._pose(sample)
                    subject = select_current_actor(sample, row["receipt"])
                    need((subject["species"], subject["role"], subject["subjectIdentity"]) == (56, "FOLLOWER", self.follower_identity)
                         and check_movement_predicate(dict(kind="follower-settled", species=56, partySlot=2), sample),
                         "Goldenrod natural bind changed the saved follower or is not settled")
                    self.subject = subject
                self.latest = deepcopy(sample)
                self.setup_index += 1
                if on_sample: on_sample(sample, self.observed_frames)
                return self.result()
            need(row.get("requestedInput", {}).get("keys") == [] and "command" not in row,
                 "Goldenrod natural input differs")
            for sample, events, _ in validate_raw_chunk(row, self.latest):
                settling = setup and action["id"] == "warp-settle"
                self._boundary(sample, transient=settling)
                if not settling: self._pose(sample)
                self.action_frames += 1
                need(self.action_frames <= action["budget"]["maxFrames"], "Goldenrod action exceeds its frame ceiling")
                if setup:
                    self._setup_events(sample, events)
                if not setup:
                    need(self.subject is not None, "Goldenrod natural window lacks its full follower bind")
                    select_current_actor(sample, self.subject)
                    self.snapshots.append(deepcopy(sample))
                    for event in events:
                        SpawnPriorityMeasurement._event_coverage(self, event)
                        if event.get("kind") == "native-observation":
                            data = event["data"]
                            self.events.append(deepcopy(event) if data.get("observation") in SELECTED else
                                dict(frame=event["frame"], kind="native-observation", data={k:data[k] for k in (
                                    "observation", "sequence", "entryActorFrame", "returnActorFrame", "entryNativeCycle", "returnNativeCycle")}))
                        elif event.get("kind") == "native" and event.get("data", {}).get("event") == "ACTOR_DETACHED":
                            self.events.append(deepcopy(event))
                    self.observed_frames += 1
                self.latest = deepcopy(sample)
                if on_sample: on_sample(sample, self.observed_frames)
            if setup and (self._ready(action) or action["op"] == "step"
                          and self.action_frames == action["args"]["frames"]):
                if action["id"] == "warp-settle":
                    self._boundary(self.latest); self._pose(self.latest)
                    m, x, z = CASES[self.kind]["start"]
                    need(player_settled_at(self.latest, m, x, z),
                         "Goldenrod warp settle lacks its declared settled player")
                self.setup_index += 1; self.action_frames = 0
            elif not setup and self.action_frames == action["args"]["frames"]:
                self.action_index += 1; self.action_frames = 0
        except (ValueError, KeyError, TypeError, IndexError) as error:
            self.failures.append(str(error))
        return self.result()

    def finish(self):
        self.closed = True
        try:
            need(not self.failures and self.action_index == len(self.test["actions"]) and self.observed_frames == FRAMES,
                 "Goldenrod natural bounded window is incomplete")
            report = parse_record(_record(self.snapshots, self.events))
            self.outcomes = witnesses(self.kind, report, self.snapshots, self.events, self.source,
                                      setup_finalizers=self.setup_finalizers)
        except (ValueError, KeyError, TypeError, IndexError) as error:
            if not self.failures: self.failures.append(str(error))
        return self.result()

    def result(self):
        ready = self.closed and not self.failures and bool(self.outcomes)
        return dict(kind=self.kind, requirements=[CASES[self.kind]["requirement"]], acceptedProof=False,
            passed=ready, ready=ready, closed=self.closed, observedFrames=self.observed_frames,
            observedFrameUnit="completed-game-frame", failures=list(self.failures), outcomes=deepcopy(self.outcomes))
