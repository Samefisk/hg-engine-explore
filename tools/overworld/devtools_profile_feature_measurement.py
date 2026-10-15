"""Small live observers for the PB9 profile building-block cases.

The observers consume only completed public actor snapshots, the authenticated
semantic trace, and the prepared-spawn receipt already owned by devtools.
They do not patch profiles, conditions, actors, timers, or collision results.
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from tools.overworld.devtools_records import select_current_actor
from tools.overworld.normal_play_observer import MotionRecorder, complete_travel
from scripts.overworld_behavior_profile_viewer import _runtime_source_behavior_catalog
from tools.overworld.devtools_application_bank import (
    decode_application_bank, global_application, local_application,
    species_applications,
)


STALKER = "stalker-runtime-v1"
PLAYFUL = "playful-runtime-v1"
STARTLED = "startled-runtime-v1"
AMBUSH = "ambush-player-landing-v1"
FLY_IN = "fly-in-runtime-v1"
WADDLE = "waddle-runtime-v1"
FLOATY_BOUNCE = "floaty-bounce-hop-pause-v1"
HELD = "held-control-runtime-v1"
BLOCKED_FACING = "blocked-wild-facing-v1"
FOLLOWER_STOP = "follower-stop-facing-v1"
RAM_UNTIL_CRASH = "ram-until-crash-v1"
RAM_BEHIND = "ram-behind-entry-v1"
FOLLOWER_RAM = "follower-ram-pokemon-v1"
RAM_LEDGE = "ram-ledge-continuity-v1"
RAM_BRIEF_NOTICE = "ram-brief-notice-v1"
THROW_NOTICE_WALK_COMMIT = "throw-notice-walk-commit-v1"
FOLLOWER_THROW_HIT_ABORT = "follower-throw-hit-abort-v1"
FLY_IN_DURATION_FRAMES = 144
BLOCKED_FACING_FRAMES = 128


def application_index(application_id, *, allow_disabled=False):
    catalog = json.loads((Path(__file__).resolve().parents[2] /
                          "data/overworld_behavior_profiles.json").read_text())
    runtime = _runtime_source_behavior_catalog(catalog)
    matches = [i for i, a in enumerate(runtime["applications"]) if a["id"] == application_id]
    if len(matches) != 1:
        authored = [a for a in catalog["applications"] if a["id"] == application_id]
        if allow_disabled and not matches and len(authored) == 1 and authored[0].get("enabled") is False:
            return None
        raise ValueError("canonical application is missing or ambiguous: " + application_id)
    return matches[0]


FEATURES = {
    STALKER: dict(requirement="current.stalker-visibility-gate",
                  subjects=(("gastly", 92),), conditionIds=(35956,), application=application_index("apply-stalker")),
    PLAYFUL: dict(requirement="current.playful-target-and-collision",
                  subjects=(("clefairy", 35), ("clefable", 36)),
                  conditionIds=(34198, 58853), application=application_index("apply-find-playmate")),
    STARTLED: dict(requirement="current.startled-timed-retreat",
                   subjects=(("bellsprout", 69),), conditionIds=(7515,), application=application_index("apply-startled")),
    AMBUSH: dict(requirement="current.ambush-player-tile-landing",
                 subjects=(("weepinbell", 70),), conditionIds=(49529,), application=application_index("apply-ambush")),
    FLY_IN: dict(requirement="current.fly-in-uneven-height",
                 subjects=(("pidgey", 16),)),
    WADDLE: dict(requirement="current.waddle-walk-presentation-only",
                 subjects=(("bellsprout", 69),)),
    FLOATY_BOUNCE: dict(requirement="current.floaty-bounce-hop-pause",
                        subjects=(("jigglypuff", 39),)),
    HELD: dict(requirement="current.held-actor-control-resume",
               subjects=(("mankey", 56), ("rattata", 19))),
    BLOCKED_FACING: dict(requirement="current.blocked-wild-facing",
                         subjects=(("exeggcute", 102),)),
    FOLLOWER_STOP: dict(requirement="current.follower-stop-facing",
                        subjects=(("stantler", 234),), role="FOLLOWER", acquire="existing"),
    RAM_UNTIL_CRASH: dict(requirement="current.ram-until-crash",
                         subjects=(("onix", 95),), conditionIds=(20305,),
                         application=application_index("apply-ram")),
    RAM_BEHIND: dict(requirement="current.ram-behind-entry",
                       subjects=(("onix",95),), conditionIds=(20305,), application=application_index("apply-ram")),
    FOLLOWER_RAM: dict(requirement="current.follower-ram-pokemon",
                       subjects=(("onix",95),("snorlax",143)), conditionIds=(49626,),
                       application=application_index("apply-ram")),
    RAM_LEDGE: dict(requirement="current.ram-ledge-continuity",
                    subjects=(("onix", 95),), conditionIds=(20305,),
                    application=application_index("apply-ram")),
    RAM_BRIEF_NOTICE: dict(requirement="current.ram-brief-notice",
                           subjects=(("onix", 95),), conditionIds=(20305,),
                           application=application_index("apply-ram")),
    THROW_NOTICE_WALK_COMMIT: dict(requirement="current.throw-notice-walk-commit",
                                   subjects=(("snorlax", 143), ("geodude", 74)),
                                   conditionIds=(24737,),
                                   application=application_index("apply-throw")),
    FOLLOWER_THROW_HIT_ABORT: dict(requirement="current.follower-throw-hit-abort",
                                   subjects=(("mankey", 56), ("onix", 95)),
                                   roles={"mankey": "FOLLOWER", "onix": "WILD"},
                                   acquires={"mankey": "existing", "onix": "spawn"},
                                   conditionIds=(12365, 26783),
                                   application=application_index("apply-throw")),
}


def require(value, reason):
    if not value:
        raise ValueError("profile feature: " + reason)


def make_measurement(kind, test=None, max_frames=600):
    if kind == FOLLOWER_STOP:
        from tools.overworld.devtools_follower_stop_measurement import FollowerStopMeasurement
        return FollowerStopMeasurement(kind, test, max_frames)
    if kind == RAM_LEDGE:
        from tools.overworld.devtools_ram_ledge_measurement import RamLedgeMeasurement
        return RamLedgeMeasurement(kind, test, max_frames)
    if kind in (RAM_UNTIL_CRASH,RAM_BEHIND):
        from tools.overworld.devtools_ram_until_crash_measurement import RamUntilCrashMeasurement
        return RamUntilCrashMeasurement(kind, test, max_frames)
    if kind == RAM_BRIEF_NOTICE:
        from tools.overworld.devtools_ram_brief_notice_measurement import RamBriefNoticeMeasurement
        return RamBriefNoticeMeasurement(kind, test, max_frames)
    if kind == THROW_NOTICE_WALK_COMMIT:
        from tools.overworld.devtools_throw_notice_walk_commit_measurement import ThrowNoticeWalkCommitMeasurement
        return ThrowNoticeWalkCommitMeasurement(kind, test, max_frames)
    if kind == FOLLOWER_THROW_HIT_ABORT:
        from tools.overworld.devtools_follower_throw_hit_abort_measurement import FollowerThrowHitAbortMeasurement
        return FollowerThrowHitAbortMeasurement(kind, test, max_frames)
    return ProfileFeatureMeasurement(kind, test, max_frames)


def _handle(actor):
    return actor.get("handle", {}).get("value")


def _tile(actor):
    return [actor["logical"]["x"], actor["logical"]["y"]]


def _distance(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def decode_condition(event):
    data = event["data"]
    reason = data["reasonId"]
    value_a = data["valueA"]
    value_b = data["valueB"]
    return {
        "frame": event["frame"],
        "actorFrame": data["actorFrame"],
        "sequence": data["sequence"],
        "application": reason & 0x1F,
        "targetSourceApplication": (reason >> 5) & 0x1F,
        "targetKind": (reason >> 10) & 0x3,
        "triggered": bool(reason & (1 << 12)),
        "truth": bool(reason & (1 << 13)),
        "active": bool(reason & (1 << 14)),
        "timed": bool(reason & (1 << 15)),
        "untilCrash": bool(value_a & (1 << 31)),
        "activationMode": "until-crash" if value_a & (1 << 31)
            else "timed" if reason & (1 << 15) else "while-true",
        "conditionId": value_a & 0xFFFF,
        "targetSlot": (value_a >> 16) & 0x7FFF,
        "activeUntil": value_b & 0xFFFF,
        "cooldownUntil": (value_b >> 16) & 0xFFFF,
    }


def _ambush_event_owner(event, subject):
    data = event.get("data", {})
    handle = subject["handle"]
    return data.get("actorHandle") == handle["value"] and data.get("actor") == {
        key: handle[key] for key in handle if key != "value"}


def ambush_exit_evidence(meter, contact_frame):
    """A native shared step is distinct from Actor Hop and Player knockback.

    Commands 0x34..0x37 are the existing shared one-tile Hop exits. Their
    accepted native owner checks profile terrain and stock blocked direction
    before setting SINGLE_MOVEMENT. Observe that command's complete actor
    travel; a request, another actor, or a Player displacement gives no credit.
    """
    subject = meter["subjects"]["weepinbell"]
    samples, events = meter["samples"], meter["events"]
    directions = {52: (0, -1), 53: (0, 1), 54: (-1, 0), 55: (1, 0)}
    identity_keys = ("handle", "subjectIdentity", "species", "role",
                     "authorityGeneration", "engineAnchorGeneration",
                     "presentationGeneration")
    for index, start in enumerate(samples):
        command = start.get("native", {}).get("command")
        if index == 0 or command not in directions or start["frame"] <= contact_frame:
            continue
        overlap = samples[index - 1]
        owner = overlap.get("owner", {})
        origin = overlap["logical"]
        center = [(v << 16) + 0x8000 for v in origin]
        if (any(owner.get(k) != subject.get(k) for k in identity_keys)
                or overlap["motionKind"] != "NONE" or overlap["motionPhase"] != "IDLE"
                or overlap.get("reservationId") != 0
                or overlap["render"][::2] != center or overlap["offsetY"] != 0
                or overlap["player"]["tile"] != origin
                or overlap["player"].get("render", [])[::2] != center
                or overlap["player"].get("offsetY") != 0
                or overlap["render"][1] != overlap["player"]["render"][1]
                or overlap.get("native", {}).get("flags", 0) & 2
                or overlap.get("native", {}).get("command") not in (0, 1, 2, 3, 255)
                or not start.get("native", {}).get("flags", 0) & 2
                or start["render"] != overlap["render"]):
            continue
        # The overlap follows an actual complete Hop of this same lifetime.
        landed = next((motion for motion in meter["motions"]
                       if motion.get("handle") == subject["handle"]
                       and motion.get("kind") == "HOP" and complete_travel(motion)
                       and contact_frame <= motion.get("finishFrame", -1) <= overlap["frame"]
                       and motion.get("terminalLogical") == origin
                       and motion.get("commitAfter") == overlap["commitSequence"]), None)
        if landed is None:
            continue
        terminal = [e for e in events if e["frame"] == landed["finishFrame"]
                    and _ambush_event_owner(e, subject)]
        names = ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")
        terminal = [next((e for e in terminal if e["data"].get("event") == name), None)
                    for name in names]
        if any(e is None for e in terminal) or not all(
                a["data"]["sequence"] < b["data"]["sequence"]
                for a, b in zip(terminal, terminal[1:])):
            continue
        dx, dy = directions[command]
        target = [origin[0] + dx, origin[1] + dy]
        target_center = [(v << 16) + 0x8000 for v in target]
        path, previous_progress = [], -1
        for row in samples[index:]:
            expected_frame = start["frame"] + len(path)
            if (row["frame"] != expected_frame
                    or any(row.get("owner", {}).get(k) != subject.get(k) for k in identity_keys)
                    or row.get("context") != overlap.get("context")
                    or row["commitSequence"] != overlap["commitSequence"]
                    or row["logical"] not in (origin, target)
                    or not row.get("native", {}).get("flags", 0) & 1
                    or row["offsetY"] != 0 or row["render"][1] != overlap["render"][1]
                    or row["player"]["tile"] == target
                    or target in row.get("otherActorTiles", [])):
                break
            x, z = row["render"][0], row["render"][2]
            progress = (x - center[0]) * dx + (z - center[1]) * dy
            on_axis = (z == center[1] if dx else x == center[0])
            if not on_axis or not 0 <= progress <= 65536 or progress <= previous_progress:
                break
            path.append(row)
            previous_progress = progress
            if [x, z] == target_center:
                if row["logical"] != target:
                    break
                # The normal profile resumes from the completed native exit.
                successor = next((r for r in samples[index + len(path) - 1:]
                                  if r["origin"] == target and r["elapsed"] == 0
                                  and r["motionKind"] == "HOP" and r["motionPhase"] == "MOVING"
                                  and r["render"][::2] == target_center
                                  and r.get("owner") == row.get("owner")
                                  and r.get("context") == row.get("context")
                                  and r["commitSequence"] == row["commitSequence"]
                                  and r["behaviorFingerprint"] != 0
                                  and r.get("profileCurrent") is True), None)
                if successor is None:
                    break
                starts = [e for e in events if e["frame"] == successor["frame"]
                          and _ambush_event_owner(e, subject)]
                intent = next((e for e in starts if e["data"].get("event") == "INTENT_CREATED"), None)
                begun = next((e for e in starts if e["data"].get("event") == "MOTION_STARTED"), None)
                if intent is None or begun is None or intent["data"]["sequence"] >= begun["data"]["sequence"]:
                    break
                if any(e["data"].get("event") in ("MOTION_CANCELED", "ACTOR_DETACHED", "ACTOR_REBOUND")
                       and _ambush_event_owner(e, subject)
                       and meter.get("initial", {}).get("frame", 0) <= e["frame"]
                           <= successor["frame"] for e in events):
                    break
                return {"handle": deepcopy(subject["handle"]), "overlapFrame": overlap["frame"],
                        "exitStartFrame": start["frame"], "exitEndFrame": row["frame"],
                        "nextStartFrame": successor["frame"], "origin": origin, "target": target,
                        "baseY": overlap["render"][1], "nativeCommand": command,
                        "travelFrames": [r["frame"] for r in path],
                        "nextIntent": deepcopy(intent), "nextStart": deepcopy(begun)}
            if (row["motionKind"] != "NONE" or row["motionPhase"] != "IDLE"
                    or row.get("reservationId") != 0
                    or row.get("native", {}).get("command") != command
                    or not row.get("native", {}).get("flags", 0) & 2):
                break
    return None


class ProfileFeatureMeasurement:
    def __init__(self, kind, test=None, max_frames=600):
        require(kind in FEATURES, "unknown feature kind")
        require(type(max_frames) is int and 1 <= max_frames <= 2000,
                "invalid frame bound")
        self.kind = kind
        self.config = FEATURES[kind]
        self.test = test
        self.max_frames = max_frames
        self.subject = None
        self.subjects = {}
        self.initial = self.terminal = self.last = None
        self.frames = 0
        self.failures = []
        self.conditions = []
        self.events = []
        self.motion = MotionRecorder()
        if kind == FLOATY_BOUNCE:
            # The contract is authored independently of the runtime's
            # resolved value, so an old zero-pause ROM fails the recorder.
            self.motion.expected_pause_by_kind["HOP"] = 10
        self.prepared = []
        self.samples = []
        self.held_open_frame = None
        self.held_closed_frame = None
        self.held_motion_starts = 0
        self.held_sync_render = None
        self.floaty_profile = None
        self.floaty_initial_motion = None
        self.floaty_recording_started = False

    def observe_prepared(self, receipt, snapshot):
        try:
            for event in receipt.get("events", []):
                data = event.get("data", {})
                if event.get("kind") != "native-observation" \
                        or data.get("observation") != "spawn-prepared":
                    continue
                encounter = data.get("preparedEncounter", {})
                if encounter.get("species") not in {item[1] for item in self.config["subjects"]}:
                    continue
                self.prepared.append(deepcopy(data))
                require(len(self.prepared) <= len(self.config["subjects"]),
                        "duplicate prepared spawn receipt")
                handle = data.get("publicSubject", {}).get("handle", {}).get("value")
                self.events.extend(deepcopy(item) for item in receipt.get("events", [])
                                   if item.get("kind") == "native"
                                   and item.get("data", {}).get("actorHandle") == handle)
        except (ValueError, KeyError, TypeError) as error:
            self.failures.append(str(error))
        return self.result()

    def _discover(self, snapshot):
        found = {}
        for name, species in self.config["subjects"]:
            candidates = [actor for actor in snapshot.get("actors", [])
                          if actor.get("active") is True
                          and actor.get("role") == "WILD"
                          and actor.get("species") == species
                          and actor.get("identityVerified") is True
                          and actor.get("presentationAttached") is True]
            if len(candidates) != 1:
                return False
            found[name] = select_current_actor(snapshot, candidates[0])
        self.subjects = found
        self.subject = deepcopy(found[self.config["subjects"][0][0]])
        self.application_bank = None
        self.local_application = self.config.get("application")
        blob_path = Path(__file__).resolve().parents[2] / "build/OverworldWildBehaviorData.bin"
        if blob_path.exists():
            self.application_bank = decode_application_bank(
                blob_path.read_bytes(), Path(__file__).resolve().parents[2])
            if self.config.get("application") is not None:
                self.local_application = local_application(
                    self.application_bank, self.subject["species"], self.config["application"])
        if self.kind == BLOCKED_FACING:
            cell = next((item for item in snapshot.get("terrain", {}).get("cells", [])
                         if item.get("x") == 580 and item.get("y") == 409), None)
            require(cell is not None and cell.get("loaded") is True
                    and cell.get("collision") is True
                    and cell.get("surface", {}).get("present") is True
                    and cell["surface"].get("type") == "canopy",
                    "Exeggcute is not on the blocked canopy fixture")
        if self.kind == AMBUSH:
            actor = next(item for item in snapshot["actors"]
                         if item.get("handle") == found["weepinbell"]["handle"])
            if actor.get("motionKind") != "NONE" or actor.get("motionPhase") != "IDLE":
                self.subjects = {}
                self.subject = None
                return False
            require(snapshot.get("context", {}).get("mapId") == 33
                    and [snapshot["player"]["x"], snapshot["player"]["y"]]
                        == [585, 408]
                    and _tile(actor) == [583, 406],
                    "Ambush fixture or initial Wild tile differs")
        self.initial = deepcopy(snapshot)
        return True

    def _actors(self, snapshot):
        result = {}
        for name, selected in self.subjects.items():
            current = select_current_actor(snapshot, selected)
            actor = next(item for item in snapshot["actors"]
                         if item.get("handle") == current["handle"])
            require(actor.get("identityVerified") is True
                    and actor.get("presentationAttached") is True,
                    name + " identity or presentation changed")
            result[name] = actor
        return result

    def _condition_event(self, event, primary_handle):
        return event.get("kind") == "native" \
            and event.get("data", {}).get("event") == "CONDITIONAL_RESOLVED" \
            and event["data"].get("actorHandle") == primary_handle

    def _sample(self, snapshot, actors):
        primary_name = self.config["subjects"][0][0]
        actor = actors[primary_name]
        engine = actor.get("engineObject", {})
        require(all(type(engine.get(key)) is int for key in
                    ("pos_x", "pos_y", "pos_z", "unk88_y", "facing")),
                "primary engine pose is missing")
        if self.kind == FLOATY_BOUNCE:
            self._observe_floaty_motion(snapshot["frame"], actor, engine)
        else:
            self.motion.observe(snapshot["frame"], actor, engine)
        sample = {
            "frame": snapshot["frame"],
            "motionKind": actor["motionKind"],
            "motionPhase": actor["motionPhase"],
            "elapsed": actor["motionElapsed"],
            "duration": actor["motionDuration"],
            "logical": _tile(actor),
            "origin": [actor["origin"]["x"], actor["origin"]["y"]],
            "target": [actor["target"]["x"], actor["target"]["y"]],
            "render": [engine["pos_x"], engine["pos_y"], engine["pos_z"]],
            "offsetY": engine["unk88_y"],
            "facing": engine["facing"],
            "commitSequence": actor["commitSequence"],
            "behaviorFingerprint": actor["behaviorFingerprint"],
            "matchedLayerMask": actor["matchedLayerMask"],
            "player": {
                "tile": [snapshot["player"]["x"], snapshot["player"]["y"]],
                "facing": snapshot["player"]["facing"],
            },
            "subjectStates": {
                name: {
                    "tile": _tile(item),
                    "motionKind": item["motionKind"],
                    "motionPhase": item["motionPhase"],
                    "commitSequence": item["commitSequence"],
                    "behaviorFingerprint": item["behaviorFingerprint"],
                    "matchedLayerMask": item["matchedLayerMask"],
                    "render": [item["engineObject"]["pos_x"],
                               item["engineObject"]["pos_y"],
                               item["engineObject"]["pos_z"]],
                    "offsetY": item["engineObject"]["unk88_y"],
                }
                for name, item in actors.items()
            },
        }
        if self.kind == AMBUSH:
            sample.update(
                owner={key: deepcopy(actor[key]) for key in (
                    "handle", "subjectIdentity", "species", "role",
                    "authorityGeneration", "engineAnchorGeneration", "presentationGeneration")},
                context=deepcopy(snapshot["context"]), reservationId=actor["reservationId"],
                profileCurrent=(snapshot.get("nativeObservation", {}).get("coverageComplete") is True
                    and snapshot["nativeObservation"].get("profilesEvicted") == 0
                    and actor["behaviorFingerprint"] in
                        snapshot["nativeObservation"].get("profileFingerprints", ())),
                native={"command": engine["movement_cmd"], "flags": engine["flags"]},
                otherActorTiles=[_tile(item) for item in snapshot["actors"]
                                 if item.get("active") is True
                                 and item.get("handle") != actor["handle"]
                                 and item.get("engineObject", {}).get("pos_y") == engine["pos_y"]])
            sample["player"].update(
                render=[snapshot["player"][key] for key in ("pos_x", "pos_y", "pos_z")],
                offsetY=snapshot["player"]["unk88_y"])
        if self.kind == FLY_IN:
            sample["shadowPolicy"] = deepcopy(actor.get("shadowPolicy"))
        if self.kind == WADDLE and actor["motionKind"] == "WALK" \
                and actor["motionDuration"]:
            dx = actor["target"]["x"] - actor["origin"]["x"]
            dz = actor["target"]["y"] - actor["origin"]["y"]
            progress_x = ((dx << 16) * actor["motionElapsed"]) // actor["motionDuration"]
            progress_z = ((dz << 16) * actor["motionElapsed"]) // actor["motionDuration"]
            straight_x = (actor["origin"]["x"] << 16) + 0x8000 + progress_x
            straight_z = (actor["origin"]["y"] << 16) + 0x8000 + progress_z
            sample["swayOffset"] = (engine["pos_z"] - straight_z
                                    if dx else engine["pos_x"] - straight_x)
        elif self.kind == WADDLE and actor["motionKind"] == "NONE" \
                and actor["motionPhase"] == "IDLE":
            center_x = (actor["logical"]["x"] << 16) + 0x8000
            center_z = (actor["logical"]["y"] << 16) + 0x8000
            sample["swayOffset"] = max(abs(engine["pos_x"] - center_x),
                                       abs(engine["pos_z"] - center_z))
        self.samples.append(sample)
        require(len(self.samples) <= self.max_frames, "sample bound exceeded")

    def _observe_floaty_motion(self, frame, actor, engine):
        motion = (actor["motionKind"], actor["origin"]["x"],
                  actor["origin"]["y"], actor["target"]["x"],
                  actor["target"]["y"])
        if self.floaty_initial_motion is None:
            self.floaty_initial_motion = motion
            self.floaty_recording_started = motion[0] == "NONE"
        if not self.floaty_recording_started:
            # A spawn Hop is already in flight at the prepared bind. Its
            # commit increments during SETTLING, but it is still the same
            # incomplete setup motion. Wait for idle or a genuinely new Hop
            # start before giving frames to the complete-motion recorder.
            if actor["motionKind"] == "NONE" and actor["motionPhase"] == "IDLE":
                self.floaty_recording_started = True
            elif motion != self.floaty_initial_motion \
                    and actor["motionPhase"] in ("PLANNED", "MOVING") \
                    and actor["motionElapsed"] in (0, 1):
                self.floaty_recording_started = True
        if self.floaty_recording_started:
            self.motion.observe(frame, actor, engine)

    def _observe_held_state(self, snapshot, actors):
        carrier = actors["mankey"]
        target = actors["rattata"]
        carrier_render = tuple(carrier["engineObject"][key]
                               for key in ("pos_x", "pos_y", "pos_z"))
        target_render = tuple(target["engineObject"][key]
                              for key in ("pos_x", "pos_y", "pos_z"))
        synchronized = carrier_render == target_render
        target_idle = target["motionKind"] == "NONE" \
            and target["motionPhase"] == "IDLE"

        # One shared tile is only overlap. HELD begins when the idle target
        # follows the carrier's changing rendered position across completed
        # frames. This is the first public effect of carried control.
        if self.held_open_frame is None:
            if synchronized and target_idle \
                    and self.held_sync_render is not None \
                    and carrier_render != self.held_sync_render:
                self.held_open_frame = snapshot["frame"]
        elif self.held_closed_frame is None \
                and (not synchronized or not target_idle):
            # The target's throw motion is the release boundary. Its first
            # completed frame can still share the carrier's rendered
            # position, so waiting for spatial divergence misclassifies that
            # release command as autonomous work while HELD.
            self.held_closed_frame = snapshot["frame"]

        self.held_sync_render = carrier_render if synchronized else None

    def _observe_floaty_profile(self, snapshot, actor):
        native = snapshot.get("nativeObservation", {})
        fingerprint = actor["behaviorFingerprint"]
        require(native.get("coverageComplete") is True
                and native.get("profilesEvicted") == 0
                and fingerprint in native.get("profileFingerprints", ()),
                "Jigglypuff profile coverage or fingerprint is missing")
        profiles = native.get("resolvedProfiles")
        if profiles is None:
            # Completed-frame samples omit bulky resolver bytes by design.
            # Only a receipt captured at the coherent setup boundary may
            # authenticate those samples; the public actor and native cache
            # must keep naming the same immutable resolved profile.
            require(self.floaty_profile is not None
                    and self.floaty_profile["fingerprint"] == fingerprint,
                    "Jigglypuff has no cached exact resolved profile receipt")
            return
        require(isinstance(profiles, list),
                "Jigglypuff resolved profile cache is invalid")
        matching = [value for value in profiles
                    if value.get("resolved") is True
                    and value.get("fingerprint") == fingerprint]
        require(len(matching) == 1,
                "Jigglypuff has no exact resolved profile receipt")
        receipt = matching[0]
        lane = bytes.fromhex(receipt["lanes"][0])
        require(len(lane) == 80 and receipt["resultHex"][:160]
                == lane.hex(), "Jigglypuff owner lane differs")
        profile = {
            "fingerprint": receipt["fingerprint"],
            "sourceSha256": receipt["sourceSha256"],
            "locomotion": lane[12], "hopPause": lane[22],
            "hopTime": lane[36],
        }
        require(self.floaty_profile is None or profile == self.floaty_profile,
                "Jigglypuff resolved profile changed during observation")
        self.floaty_profile = profile

    def observe(self, snapshot, events):
        if self.failures:
            return self.result()
        try:
            if not self.subjects and not self._discover(snapshot):
                return self.result()
            if self.last is not None:
                require(snapshot.get("frame") == self.last.get("frame") + 1,
                        "completed-frame stream has a gap")
            actors = self._actors(snapshot)
            primary = actors[self.config["subjects"][0][0]]
            if self.kind == FLOATY_BOUNCE:
                self._observe_floaty_profile(snapshot, primary)
            if self.kind == BLOCKED_FACING:
                require(snapshot.get("context") == self.initial.get("context"),
                        "blocked Exeggcute field context changed")
            if self.kind == AMBUSH:
                require(snapshot.get("context") == self.initial.get("context"),
                        "Ambush field moved during the landing and exit test")
            if self.kind == HELD:
                self._observe_held_state(snapshot, actors)
            self.frames += 1
            require(self.frames <= self.max_frames, "frame bound exceeded")
            for event in events:
                if event.get("kind") == "trace-status":
                    data = event.get("data", {})
                    if data.get("code") == "ring-overwrite":
                        require(type(data.get("unreadEventsLost")) is int
                                and data["unreadEventsLost"] == 0
                                and data.get("coverageComplete", True) is True
                                and data.get("diagnosticOnly") is True
                                and type(data.get("count")) is int
                                and data["count"] > 0
                                and type(data.get("traceStream")) is int
                                and data["traceStream"] > 0,
                                "semantic trace coverage is incomplete")
                    else:
                        require(data.get("code") not in
                                ("unread-events-lost", "sequence-reset",
                                 "invalid-native-ring", "trace-filter-changed"),
                                "semantic trace coverage is incomplete")
                if event.get("kind") == "native" \
                        and event.get("data", {}).get("actorHandle") in {
                            _handle(actor) for actor in actors.values()}:
                    self.events.append(deepcopy(event))
                    if self.kind == AMBUSH:
                        require(event["data"].get("event") not in
                                ("MOTION_CANCELED", "ACTOR_DETACHED", "ACTOR_REBOUND", "CONTEXT_CHANGED"),
                                "Ambush landing or shared exit lost its native actor lifecycle")
                    if self.kind == BLOCKED_FACING:
                        require(event["data"].get("event") not in
                                ("MOTION_STARTED", "LOGICAL_COMMIT", "MOTION_CANCELED"),
                                "blocked Exeggcute started or committed motion")
                if self._condition_event(event, _handle(primary)):
                    decoded = decode_condition(event)
                    if decoded["application"] == self.local_application \
                            and decoded["conditionId"] in self.config.get("conditionIds", ()):
                        if self.application_bank is not None:
                            decoded["applicationLocal"] = decoded["application"]
                            decoded["targetSourceApplicationLocal"] = decoded["targetSourceApplication"]
                            decoded["application"] = global_application(
                                self.application_bank, primary["species"], decoded["applicationLocal"])
                            applications = species_applications(self.application_bank, primary["species"])
                            source = decoded["targetSourceApplicationLocal"]
                            decoded["targetSourceApplication"] = (
                                applications[source] if source < len(applications) else None)
                        self.conditions.append(decoded)
            if self.kind == HELD and self.held_open_frame is not None \
                    and self.held_closed_frame is None:
                rattata_handle = _handle(actors["rattata"])
                self.held_motion_starts += sum(
                    event.get("kind") == "native"
                    and event.get("data", {}).get("event") == "MOTION_STARTED"
                    and event["data"].get("actorHandle") == rattata_handle
                    for event in events)
            self._sample(snapshot, actors)
            if self.kind == AMBUSH:
                complete = [motion for motion in self.motion.completed
                            if self._complete_motion(motion)]
                # Normal contact can knock the Player back on the terminal
                # frame. Keep the stationary setup until this actual landing.
                if self._ambush_evidence(complete) is None:
                    require([snapshot["player"]["x"], snapshot["player"]["y"]] == [585, 408],
                            "Ambush player moved before the original landing")
            if self.kind == BLOCKED_FACING:
                first = self.samples[0]
                current = self.samples[-1]
                require(current["logical"] == [580, 409]
                        and current["motionKind"] == "NONE"
                        and current["motionPhase"] == "IDLE"
                        and current["commitSequence"] == first["commitSequence"]
                        and current["facing"] == first["facing"],
                        "blocked Exeggcute moved, committed, or changed facing")
            self.last = deepcopy(snapshot)
            if self.ready:
                self.terminal = deepcopy(snapshot)
        except (ValueError, KeyError, TypeError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def _events(self, name, *, actor_name=None, after=None, before=None):
        handle = _handle(self.subjects[actor_name]) if actor_name else None
        return [event for event in self.events
                if event.get("data", {}).get("event") == name
                and (handle is None or event["data"].get("actorHandle") == handle)
                and (after is None or event["frame"] >= after)
                and (before is None or event["frame"] < before)]

    def _complete_motion(self, motion):
        if complete_travel(motion):
            return True
        if motion.get("kind") != "FLY_IN" or not self.prepared:
            return False
        samples = motion.get("samples", [])
        end = motion.get("travelEnd")
        if (not samples or end is None
                or motion.get("duration") != FLY_IN_DURATION_FRAMES):
            return False
        elapsed = [sample.get("elapsed") for sample in samples]
        frames = [sample.get("frame") for sample in samples]
        prepared = self.prepared[0]
        startup = prepared.get("startup", {})
        public = prepared.get("publicSubject", {})
        # The authenticated prepared-spawn bridge returns on elapsed frame 2.
        # Retain every public sample from that first observable boundary to
        # the terminal sample and anchor the omitted 0/1 pair to the native
        # prepared receipt that created this exact Fly In motion.
        return elapsed[0] == 2 \
            and elapsed == list(range(2, motion["duration"])) \
            and all(second == first + 1
                    for first, second in zip(frames, frames[1:])) \
            and end.get("elapsed") == motion["duration"] \
            and end.get("frame") == frames[-1] + 1 \
            and motion.get("terminalLogical") == motion.get("target") \
            and prepared.get("observation") == "spawn-prepared" \
            and prepared.get("setupMode") == "prepared" \
            and startup.get("locomotion") == 9 \
            and startup.get("origin") == motion.get("origin") \
            and startup.get("target") == motion.get("target") \
            and public.get("motionKind") == "FLY_IN" \
            and public.get("motionPhase") == "MOVING" \
            and public.get("handle") == motion.get("handle")

    def _stalker_evidence(self, complete):
        active = next((row for row in self.conditions if row["active"]), None)
        if active is None:
            return None
        for active_motion in complete:
            if active_motion["startFrame"] < active["frame"]:
                continue
            active_sample = next((sample for sample in self.samples
                                  if sample["frame"] >= active_motion["startFrame"]
                                  and sample["behaviorFingerprint"]
                                      == active_motion["fingerprint"]), None)
            if active_sample is None:
                continue
            finish = active_motion.get(
                "finishFrame",
                active_motion.get("travelEnd", {}).get("frame", active_motion["startFrame"]),
            )
            transition = next((sample for sample in self.samples
                               if sample["frame"] >= finish
                               and sample["behaviorFingerprint"]
                                   != active_motion["fingerprint"]
                               and sample["matchedLayerMask"]
                                   != active_sample["matchedLayerMask"]
                               and _distance(sample["logical"], sample["player"]["tile"])
                                   <= 1), None)
            if transition is None:
                continue
            routine = next((motion for motion in complete
                            if motion["startFrame"] >= transition["frame"]
                            and motion["fingerprint"]
                                == transition["behaviorFingerprint"]), None)
            if routine is not None:
                return active, active_motion, transition, routine
        return None

    def _ambush_evidence(self, complete):
        active = [row for row in self.conditions
                  if row["active"] and row["timed"]
                  and row["conditionId"] == 49529
                  and row["application"] == self.config["application"]
                  and row["targetSourceApplication"] == self.config["application"]
                  and row["targetKind"] == 1]
        handle = _handle(self.subjects["weepinbell"])
        for motion in complete:
            if (motion["kind"] != "HOP" or motion["target"] != [585, 408]
                    or motion["terminalLogical"] != [585, 408]):
                continue
            sample = next((row for row in self.samples
                           if row["frame"] == motion["startFrame"]
                           and row["behaviorFingerprint"] == motion["fingerprint"]
                           and row["matchedLayerMask"] & (1 << self.local_application)), None)
            condition = next((row for row in active
                              if row["frame"] <= motion["startFrame"]
                              and motion["startFrame"] - row["frame"] <= 1), None)
            if sample is None or condition is None:
                continue
            names = ("INTENT_CREATED", "MOTION_STARTED", "LOGICAL_COMMIT",
                     "MOTION_FINISHED", "CONTROL_RETURNED")
            events = []
            for name in names:
                event = next((event for event in self._events(name, actor_name="weepinbell")
                              if motion["startFrame"] <= event["frame"]
                                  <= motion["finishFrame"]
                              and (not events or event["data"]["sequence"]
                                   > events[-1]["data"]["sequence"])), None)
                if event is None:
                    break
                events.append(event)
            if len(events) != len(names):
                continue
            if motion["commitAfter"] != motion["commitBefore"] + 1:
                continue
            return condition, motion, sample, events
        return None

    @property
    def ready(self):
        if self.failures or not self.subjects:
            return False
        complete = [motion for motion in self.motion.completed
                    if self._complete_motion(motion)]
        triggered = [row for row in self.conditions if row["triggered"] and row["active"]]
        if self.kind == STALKER:
            return self._stalker_evidence(complete) is not None
        if self.kind == PLAYFUL:
            ids = {row["conditionId"] for row in triggered}
            return ids == set(self.config["conditionIds"]) and len(complete) >= 2
        if self.kind == STARTLED:
            if not triggered:
                return False
            frame = triggered[0]["frame"]
            starts = self._events("MOTION_STARTED", after=frame,
                                  before=frame + 44)
            returns = self._events("CONTROL_RETURNED", after=frame + 44)
            return len(starts) >= 2 and bool(complete) and bool(returns)
        if self.kind == AMBUSH:
            landing = self._ambush_evidence(complete)
            return landing is not None and ambush_exit_evidence(
                {"subjects": self.subjects, "initial": self.initial,
                 "samples": self.samples, "events": self.events,
                 "motions": self.motion.completed},
                landing[1]["finishFrame"]) is not None
        if self.kind == FLY_IN:
            return any(motion["kind"] == "FLY_IN" for motion in complete) \
                and bool(self._events("LOGICAL_COMMIT", actor_name="pidgey")) \
                and bool(self._events("CONTROL_RETURNED", actor_name="pidgey"))
        if self.kind == WADDLE:
            return any(motion["kind"] == "WALK" for motion in complete) \
                and any(sample["motionKind"] == "NONE"
                        and sample["motionPhase"] == "IDLE"
                        for sample in self.samples) \
                and bool(self._events("LOGICAL_COMMIT", actor_name="bellsprout")) \
                and bool(self._events("CONTROL_RETURNED", actor_name="bellsprout"))
        if self.kind == FLOATY_BOUNCE:
            hops = [motion for motion in complete
                    if motion["kind"] == "HOP"
                    and motion["startFrame"] > self.initial["frame"]]
            return len(hops) >= 2 and bool(self.floaty_profile) \
                and len(self._events("CONTROL_RETURNED", actor_name="jigglypuff",
                                     after=hops[0]["startFrame"])) >= 2
        if self.kind == HELD:
            if self.held_closed_frame is None or self.held_motion_starts:
                return False
            return bool(self._events("MOTION_STARTED", actor_name="mankey",
                                     after=self.held_closed_frame))
        if self.kind == BLOCKED_FACING:
            return len(self.samples) >= BLOCKED_FACING_FRAMES
        return False

    @property
    def closed(self):
        return self.ready

    def stage(self, name):
        if self.kind == PLAYFUL and name == "actor-play-complete":
            actor_triggers = [row for row in self.conditions
                              if row["triggered"] and row["active"]
                              and row["conditionId"] == self.config["conditionIds"][0]]
            player_triggers = [row for row in self.conditions
                               if row["triggered"] and row["active"]
                               and row["conditionId"] == self.config["conditionIds"][1]]
            complete = [motion for motion in self.motion.completed
                        if self._complete_motion(motion)]
            return bool(actor_triggers and not player_triggers
                        and any(motion["startFrame"] >= actor_triggers[0]["frame"]
                                for motion in complete))
        if self.kind != STALKER or name != "unseen-motion-complete":
            return False
        active = [row for row in self.conditions if row["active"]]
        complete = [motion for motion in self.motion.completed
                    if self._complete_motion(motion)]
        return bool(active and any(motion["startFrame"] >= active[0]["frame"]
                                   for motion in complete))

    def finish(self):
        if self.kind == FLOATY_BOUNCE and not self.ready and not self.failures:
            complete = [motion for motion in self.motion.completed
                        if self._complete_motion(motion) and motion["kind"] == "HOP"
                        and motion["startFrame"] > self.initial["frame"]]
            if len(complete) >= 2 and self.floaty_profile \
                    and len(self._events("CONTROL_RETURNED", actor_name="jigglypuff",
                                         after=complete[0]["startFrame"])) < 2:
                self.failures.append("Jigglypuff has fewer than two control-return events")
        if not self.ready and not self.failures:
            self.failures.append("profile feature did not complete")
        motion_failures = list(self.motion.failures)
        if self.kind == FLY_IN and any(self._complete_motion(motion)
                                       for motion in self.motion.completed):
            # Prepared spawning returns after elapsed frames 0 and 1. The
            # feature observer proves those omitted frames from the prepared
            # receipt for that exact motion, so only that exact shared-
            # recorder complaint is expected here.
            motion_failures = [item for item in motion_failures
                               if not (item.get("reason") == "incomplete-travel"
                                       and item.get("motion") == "FLY_IN"
                                       and item.get("duration")
                                           == FLY_IN_DURATION_FRAMES
                                       and item.get("elapsed")
                                           == list(range(2, FLY_IN_DURATION_FRAMES)))
                               and not (item.get("reason") == "missed-motion-start"
                                        and item.get("elapsed") == 2)]
        if motion_failures:
            self.failures.extend("motion: " + item["reason"]
                                 for item in motion_failures)
        return self.result()

    def result(self):
        return {
            "kind": self.kind,
            "requirements": [self.config["requirement"]],
            "passed": self.ready and not self.failures,
            "ready": self.ready,
            "closed": self.closed,
            "acceptedProof": False,
            "failures": list(self.failures),
            "frames": self.frames,
            "subject": deepcopy(self.subject),
            "subjects": deepcopy(self.subjects),
            "initial": deepcopy(self.initial),
            "terminal": deepcopy(self.terminal),
            "conditions": deepcopy(self.conditions),
            "events": deepcopy(self.events),
            "motions": deepcopy(self.motion.completed),
            "prepared": deepcopy(self.prepared),
            "samples": deepcopy(self.samples),
            "heldOpenFrame": self.held_open_frame,
            "heldClosedFrame": self.held_closed_frame,
            "heldMotionStarts": self.held_motion_starts,
            "floatyProfile": deepcopy(self.floaty_profile),
        }
