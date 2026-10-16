"""Measure a real Wild Throw that misses the offset mounted rider.

Prepared placement establishes two current actors. Only subsequent normal
movement, flight, and HP observations count toward the gameplay claim.
"""

from copy import deepcopy
import struct

from scripts.overworld_behavior_profile_viewer import _stable_condition_id
from tools.overworld.devtools_follower_throw_measurement import raw_handle
from tools.overworld.devtools_profile_feature_measurement import application_index

from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_mount_gait import check_gait
from tools.overworld.devtools_mount_pacing_measurement import check_pair_pose
from tools.overworld.devtools_movement_predicates import player_settled_at
from tools.overworld.devtools_walk_matrix_observer import decode_motion


KIND = "player-health-mounted-throw-v1"
REQUIREMENT = "current.player-health-mounted-throw"
SETUP = ("throw-tile", "prepare-cyndaquil", "mount-cyndaquil", "settle-mount",
         "bind-cyndaquil", "spawn-geodude", "bind-geodude",
         "capture-player-trigger", "spawn-bellsprout", "bind-bellsprout")
ORDER = ("before-throw", "launch-natural-throw", "at-launch",
         "cross-player", "after-contact")
LAUNCH_LIMIT = 240
TRIGGER_LIMIT = 60
TRIGGER_CONDITION = _stable_condition_id("throw", "condition-throw-notices-player")
TRIGGER_APPLICATION = application_index("apply-throw")
CROSS_FRAMES = 64
MIN_FRAMES = 1 + CROSS_FRAMES
PLAYER_TILE = (585, 407)
KNOCKBACK_TILE = (585, 408)
TARGET_START = (585, 403)
SOURCE_START = (585, 404)
# Current physical application ID: apply-throw-release22.
THROW_RELEASE_BIT = 1 << application_index("apply-throw-release")
# The current throw-find-position profile admits the full north line.
THROW_MAX_RANGE = 8
HALF_TILE = 0x8000


def require(value, message):
    if not value:
        raise ValueError(message)


class PlayerHealthMountedThrowMeasurement:
    def __init__(self, source):
        self.source = source
        self.latest = None
        self.subjects = {}
        self.receipts = {}
        self.setup_index = 0
        self.settle_frames = 0
        self.trigger_frame = None
        self.trigger_frames = 0
        self.action_index = 0
        self.observed_frames = 0
        self.launch_frames = 0
        self.cross_frames = 0
        self.launch_frame = None
        self.flight_frames = 0
        self.travel_seen = False
        self.old_box_crossed = False
        self.landed = False
        self.flight_origin = None
        self.flight_duration = None
        self.flight_reservation = None
        self.flight_commit = None
        self.flight_plan = None
        self.flight_terminal = None
        self.previous_projectile_z = None
        self.mount_before = None
        self.mount_hit_frame = None
        self.mount_knockback = None
        self.mount_seat_restored = False
        self.failures = []

    def _boundary(self, snapshot, fixture=True):
        require(isinstance(snapshot, dict)
                and snapshot.get("observationBoundary") == "main-task-queue-completion"
                and snapshot.get("fieldAvailable") is True
                and type(snapshot.get("frame")) is int
                and type(snapshot.get("nativeCycle")) is int,
                "Throw proof needs a completed game boundary")
        context = snapshot.get("context", {})
        require(isinstance(context, dict)
                and (not fixture or context.get("mapId") == 33),
                "Throw proof map differs")
        require(isinstance(snapshot.get("player"), dict)
                and snapshot.get("fieldControl", {}).get("taskPointer") == 0,
                "Throw proof left normal field control or entered battle")
        if fixture:
            require((snapshot["player"].get("x"), snapshot["player"].get("y"))
                    in ((PLAYER_TILE, KNOCKBACK_TILE) if self.mount_hit_frame is not None
                        else (PLAYER_TILE,)) and snapshot["player"].get("facing") == 0,
                    "north-facing player left the mounted Throw fixture")
        if "romSha256" in snapshot:
            require(snapshot["romSha256"] == self.source["romSha256"],
                    "Throw snapshot ROM identity differs")

    def _actor(self, snapshot, subject_id):
        require(subject_id in self.subjects, "Throw actor was not bound: " + subject_id)
        selected = select_current_actor(snapshot, self.subjects[subject_id])
        actor = next(a for a in snapshot["actors"]
                     if a.get("handle") == selected["handle"])
        species, role = {"bellsprout": (69, "WILD"), "geodude": (74, "WILD"),
                         "cyndaquil": (155, "MOUNTED")}[subject_id]
        require(actor.get("species") == species and actor.get("role") == role
                and actor.get("active") is True
                and actor.get("presentationAttached") is True,
                "Throw actor is not the current visible " + subject_id)
        return actor

    def _trigger(self, sample):
        self._boundary(sample)
        self._rider(sample)
        geo = self._actor(sample, "geodude")
        combat = sample["pokemonCombat"]
        value = combat.get("interactions", {})
        require(value.get("schemaVersion") == 1 and value.get("available") is True
                and value.get("frame") == sample["frame"]
                and value.get("nativeCycle") == sample["nativeCycle"]
                and value.get("observationBoundary") == "main-task-queue-completion"
                and value.get("fieldSystem") == sample["fieldControl"]["fieldPointer"]
                and value.get("identity", {}).get("romSha256") == self.source["romSha256"],
                "mounted Throw Trigger needs current authenticated interactions")
        rows = [row for row in value.get("carriers", []) if row.get("handle") == geo["handle"]]
        require(len(rows) == 1 and rows[0].get("role") == "WILD"
                and rows[0].get("available") is True,
                "mounted Throw Trigger has no current Geodude owner")
        row = rows[0]; raw = bytes.fromhex(row.get("rawBindingsHex", ""))
        require(len(raw) == 60 and raw[:12] == raw_handle(geo["handle"]),
                "mounted Throw Trigger binding owner differs")
        bound = row["bindings"]["trigger"]; data = raw[12:36]
        require(data.hex() == bound.get("rawHex") and data[12:14] ==
                    bytes([{"NONE":0,"PLAYER":1,"ACTOR":2}.get(bound["target"]["kind"],255),0])
                and struct.unpack_from("<HIBBBB",data,14) ==
                    (bound["sourceConditionId"],bound["expiresAt"],bound["sourceApplication"],
                     bound["lifetime"],bound["flags"],bound["reason"])
                and bound["bound"] is bool(bound["flags"]),
                "mounted Throw Trigger raw binding differs")
        if not bound["bound"]:
            return False
        require(bound["target"] == {"kind":"PLAYER", "actor":None} and bound["targetCurrent"] is True
                and bound["sourceConditionId"] == TRIGGER_CONDITION
                and bound["sourceApplication"] == TRIGGER_APPLICATION and bound["expiresAt"] == 0
                and bound["lifetime"] == 0 and bound["reason"] == 0,
                "mounted Throw Trigger is not the current real Player capture")
        return ((geo["logical"]["x"],geo["logical"]["y"]) == SOURCE_START
                and geo["motionPhase"] == "IDLE" and geo["reservationId"] == 0)

    def _mount_hp(self, snapshot, mount):
        combat = snapshot.get("pokemonCombat", {})
        require(combat.get("schemaVersion") == 1 and combat.get("available") is True
                and combat.get("frame") == snapshot["frame"]
                and combat.get("nativeCycle") == snapshot["nativeCycle"]
                and combat.get("observationBoundary") == "main-task-queue-completion"
                and type(combat.get("fieldSystem")) is int
                and 0x02000000 <= combat["fieldSystem"] < 0x02400000
                and combat["fieldSystem"] == snapshot["fieldControl"].get("fieldPointer")
                and combat.get("identity") == {"descriptorVersion": 1,
                    "romSha256": self.source["romSha256"],
                    "overlaySha256": self.source["overlaySha256"]},
                "mounted Throw lacks current authenticated combat HP")
        rows = [r for r in combat.get("targets", []) if r.get("handle") == mount["handle"]]
        require(len(rows) == 1, "mounted Throw combat target is stale or missing")
        hp = rows[0]
        party = [m for m in snapshot.get("party", [])
                 if m.get("personality") == mount["subjectIdentity"]]
        require(hp.get("personality") == mount["subjectIdentity"]
                and hp.get("role") == "MOUNTED" and hp.get("species") == 155
                and hp.get("initialized") == 1 and hp.get("hpSource") == "party"
                and hp.get("hpMirrorMatches") is True
                and type(hp.get("hp")) is int and type(hp.get("maxHp")) is int
                and 0 < hp["hp"] <= hp["maxHp"] == hp.get("actualMaxHp")
                and hp["hp"] == hp.get("currentHp")
                and len(party) == 1 and party[0].get("identityVerified") is True
                and party[0].get("species") == 155
                and party[0].get("hp") == hp["hp"]
                and party[0].get("maxHp") == hp["maxHp"]
                and snapshot.get("partyObservation", {}).get("frame") == snapshot["frame"]
                and snapshot["partyObservation"].get("boundary") == "main-task-queue-completion",
                "mounted Throw HP differs from the real current party mount")
        if self.mount_before is None:
            require(hp["hp"] == hp["maxHp"] and hp.get("hitCount") == 0
                    and hp.get("lastDamage") == 0,
                    "mounted Throw must start with a full unhit mount")
            self.mount_before = dict(hp=hp["hp"], maxHp=hp["maxHp"],
                commit=mount["commitSequence"], baseY=mount["engineObject"]["pos_y"])
        require(hp["maxHp"] == self.mount_before["maxHp"],
                "mounted Throw changed the bound mount's maximum HP")
        damage = min(20, max(1, self.mount_before["maxHp"] // 2))
        if hp.get("hitCount") == 0:
            require(self.mount_hit_frame is None and hp["hp"] == self.mount_before["hp"]
                    and hp.get("lastDamage") == 0,
                    "mounted Throw changed mount HP without one real contact")
        else:
            require(hp.get("hitCount") == 1 and hp.get("lastDamage") == damage
                    and hp["hp"] == self.mount_before["hp"] - damage,
                    "mounted Throw mount contact count or capped damage differs")
            if self.mount_hit_frame is None:
                target = self._actor(snapshot, "bellsprout")
                require(self.launch_frame is not None and not self.landed
                        and target.get("motionKind") == "HOP"
                        and target.get("motionPhase") == "MOVING"
                        and target.get("origin") == dict(zip(("x", "y"), self.flight_origin))
                        and target.get("target") == dict(zip(("x", "y"), PLAYER_TILE))
                        and target.get("motionDuration") == self.flight_duration
                        and target.get("reservationId") == self.flight_reservation
                        and target.get("commitSequence") == self.flight_commit
                        and 0 < target.get("motionElapsed", 0) < self.flight_duration
                        and snapshot["player"]["pos_z"] - HALF_TILE
                            <= target.get("engineObject", {}).get("pos_z", -1)
                            < snapshot["player"]["pos_z"],
                        "mounted Throw mount hit is outside the authenticated first flight")
                self.mount_hit_frame = snapshot["frame"]
        return hp

    def _rider(self, snapshot):
        mount = self._actor(snapshot, "cyndaquil")
        hp = self._mount_hp(snapshot, mount)
        player, body = snapshot["player"], mount["engineObject"]
        pair = snapshot.get("mountedPair", {})
        require(pair.get("playerPointer") == mount["engineIdentity"].get("anchorPointer")
                and pair.get("mountPointer") == mount["engineIdentity"]["pointer"]
                and all(pair.get("player", {}).get(k) == v for k, v in player.items())
                and all(pair.get("mount", {}).get(k) == v for k, v in body.items()),
                "mounted Throw pair is not the current player and mount")
        check_gait(pair, required=True)
        check_pair_pose(pair)
        require(player.get("facing") == body.get("facing") == 0
                and player.get("pos_x") == 38371328
                and player.get("pos_y") == body.get("pos_y") == self.mount_before["baseY"]
                and player.get("face_y") == 32768 and body.get("face_y") == 0
                and mount.get("inputOwnership") == 1,
                "mounted Throw changed its north-facing seat or height")
        if mount.get("motionKind") == "HOP":
            motion = hp.get("motion", {}); plan = motion.get("plan", {})
            require(self.mount_hit_frame is not None and not self.mount_seat_restored
                    and plan.get("version") == 1 and plan.get("kind") == 2
                    and plan.get("fieldEpoch") == mount["handle"]["fieldEpoch"]
                    and plan.get("origin") == list(PLAYER_TILE)
                    and plan.get("target") == list(KNOCKBACK_TILE)
                    and plan.get("flags") == 1 and plan.get("direction") == 1
                    and plan.get("distance") == 1 and plan.get("arcHeightQ4") == 0
                    and plan.get("startBaseY") == plan.get("targetBaseY") == self.mount_before["baseY"]
                    and plan.get("pathAdvancePolicy") == 2 and plan.get("commitPolicy") == 1
                    and type(plan.get("duration")) is int and 0 < plan["duration"] <= CROSS_FRAMES
                    and type(plan.get("reservationId")) is int and plan["reservationId"] > 0,
                    "mounted Throw movement is not its one shared forced knockback")
            if self.mount_knockback is None:
                require(snapshot["frame"] == self.mount_hit_frame + 1,
                        "mounted Throw knockback did not follow its accepted mount hit")
                self.mount_knockback = deepcopy(plan)
            require(plan == self.mount_knockback
                    and mount.get("origin") == dict(zip(("x", "y"), PLAYER_TILE))
                    and mount.get("target") == dict(zip(("x", "y"), KNOCKBACK_TILE))
                    and mount.get("motionPhase") == motion.get("phase")
                        in ("MOVING", "COMMIT_PENDING")
                    and mount.get("reservationId") == plan["reservationId"]
                    and mount.get("motionDuration") == plan["duration"]
                    and mount.get("motionElapsed") == motion.get("elapsed")
                    and mount.get("commitSequence") == self.mount_before["commit"]
                    and motion.get("commitPublished") == 0 and motion.get("commitSequence") == 0
                    and type(motion.get("elapsed")) is int and 0 < motion["elapsed"] <= plan["duration"]
                    and player.get("pos_z") == 26705920 + 65536 * motion["elapsed"] // plan["duration"],
                    "mounted Throw knockback owner, plan, or applied pose differs")
        else:
            require(mount.get("motionKind") == "NONE" and mount.get("motionPhase") == "IDLE"
                    and mount.get("reservationId") == 0,
                    "mounted Throw left an active or different movement owner")
            tile = KNOCKBACK_TILE if self.mount_knockback is not None else PLAYER_TILE
            require(player.get("pos_z") == (tile[1] << 16) + HALF_TILE
                    and (mount["logical"]["x"], mount["logical"]["y"]) == tile,
                    "mounted rider did not return to its current exact seat")
            if self.mount_knockback is not None:
                motion = hp.get("motion", {})
                require(mount.get("commitSequence") == self.mount_before["commit"] + 1
                        and motion.get("phase") == "IDLE"
                        and motion.get("commitPublished") == 1 and motion.get("commitSequence") == 1
                        and motion.get("elapsed") == self.mount_knockback["duration"]
                        and player_settled_at(snapshot, 33, *KNOCKBACK_TILE),
                        "mounted Throw knockback has no completed settled seat")
                self.mount_seat_restored = True

    def _same_boundary(self, snapshot):
        keys = ("frame", "nativeCycle", "observationBoundary", "fieldAvailable",
                "romSha256", "context", "fieldControl", "player", "actors")
        require(all(snapshot.get(key) == self.latest.get(key) for key in keys),
                "Throw HP receipt is not at the current completed boundary")

    def _health(self, row, action):
        result = row.get("receipt")
        hp = result.get("playerHealth") if isinstance(result, dict) else None
        require(isinstance(hp, dict) and hp.get("schemaVersion") == 1,
                "checked Throw HP receipt is missing")
        identity = hp.get("identity", {})
        require(identity.get("descriptorVersion") == 1
                and identity.get("overlayId") == 161
                and identity.get("overlaySha256") == self.source["overlaySha256"]
                and identity.get("romSha256") == self.source["romSha256"],
                "Throw HP ROM or overlay identity differs")
        snapshot = row["snapshot"]
        self._boundary(snapshot)
        self._actor(snapshot, "bellsprout")
        self._actor(snapshot, "geodude")
        self._rider(snapshot)
        require(hp.get("frame") == snapshot["frame"]
                and hp.get("nativeCycle") == snapshot["nativeCycle"]
                and hp.get("maxHp") == 100
                and hp.get("hp") == hp.get("savedHp")
                and hp.get("recoveryPending") is False
                and hp.get("frameActive") is False,
                "Throw HP read differs from current field and save")
        expected = (100, 0, 0)
        require((hp.get("hp"), hp.get("lastDamage"), hp.get("acceptedHits"))
                == expected, "mounted Throw damaged the rider or changed saved HP")
        health_frame = hp.get("lastHealthFrame")
        require(type(health_frame) is int and health_frame >= 0,
                "Throw HP clock is missing")
        if action == "at-launch":
            require(self.launch_frame == snapshot["frame"],
                    "Throw launch HP was not read at the launch boundary")
            before = self.receipts["before-throw"]
            require(health_frame - before["lastHealthFrame"]
                    == snapshot["frame"] - before["frame"],
                    "Throw HP clock did not advance with field frames before launch")
        if action == "after-contact":
            require(self.landed and self.flight_frames > 0 and self.travel_seen
                    and self.old_box_crossed and self.mount_seat_restored,
                    "Throw missed the old base box or lacks a measured airborne crossing")
            launch = self.receipts["at-launch"]
            require(health_frame - launch["lastHealthFrame"]
                    == snapshot["frame"] - launch["frame"],
                    "Throw HP clock did not advance with the completed flight frames")
        self.receipts[action] = deepcopy(hp)

    def _cargo_motion(self, sample, cargo):
        # _rider has already authenticated this completed combat boundary.
        rows = [r for r in sample["pokemonCombat"]["targets"]
                if r.get("handle") == cargo["handle"]]
        require(len(rows) == 1 and rows[0].get("personality") == cargo["subjectIdentity"]
                and rows[0].get("species") == 69 and rows[0].get("role") == "WILD"
                and rows[0].get("initialized") == 1,
                "Throw flight motion has no current full Cargo owner")
        motion = rows[0].get("motion", {})
        require(motion == decode_motion(bytes.fromhex(motion.get("rawHex", ""))),
                "Throw flight motion bytes differ")
        return motion

    def _terminal(self, sample, cargo, events, motion):
        handle = cargo["handle"]
        native = [e["data"] for e in events if e.get("kind") == "native"
                  and e.get("data", {}).get("actorHandle") == handle["value"]]
        owner = {k: v for k, v in handle.items() if k != "value"}
        clock = sample.get("actorFrame")
        require(type(clock) is int and all(e.get("actor") == owner
                and type(e.get("frame")) is int and type(e.get("actorFrame")) is int
                and e["frame"] == e["actorFrame"] == clock
                and type(e.get("sequence")) is int for e in native),
                "Throw terminal receipt has a stale Cargo owner or Actor clock")
        terminal = {name: [e for e in native if e.get("event") == name]
                    for name in ("LOGICAL_COMMIT", "MOTION_FINISHED", "CONTROL_RETURNED")}
        committed, finished, returned = (terminal[name] for name in terminal)
        if committed:
            require(len(committed) == 1 and self.flight_terminal is None
                    and committed[0].get("reason") == "OK"
                    and committed[0].get("valueA") == self.flight_commit + 1
                    and committed[0].get("valueB") == 2
                    and cargo["commitSequence"] == self.flight_commit + 1
                    and sample["frame"] == self.launch_frame + self.flight_duration,
                    "Throw landing is not the completed first flight commit")
            self.flight_terminal = dict(frame=sample["frame"], actorFrame=clock,
                nativeCycle=sample["nativeCycle"], commitSequence=cargo["commitSequence"],
                commitEventSequence=committed[0]["sequence"], cargo=deepcopy(handle))
        if finished or returned:
            require(self.flight_terminal is not None and len(finished) == len(returned) == 1
                    and finished[0].get("reason") == returned[0].get("reason") == "OK"
                    and self.flight_terminal["commitEventSequence"] < finished[0]["sequence"]
                        < returned[0]["sequence"]
                    and finished[0].get("valueA") == self.flight_terminal["commitSequence"]
                    and finished[0].get("valueB") == 2 and returned[0].get("valueA") == 0
                    and returned[0].get("valueB") == self.flight_terminal["commitSequence"]
                    and cargo["commitSequence"] == self.flight_terminal["commitSequence"],
                    "Throw flight lacks ordered full Cargo finish and control return")
            plan = motion["plan"]
            require(cargo.get("logical") == dict(zip(("x", "y"), PLAYER_TILE))
                    and cargo.get("engineObject", {}).get("pos_x") == (PLAYER_TILE[0] << 16) + HALF_TILE
                    and cargo.get("engineObject", {}).get("pos_z") == (PLAYER_TILE[1] << 16) + HALF_TILE
                    and cargo.get("engineObject", {}).get("pos_y") == self.flight_plan["targetBaseY"],
                    "Throw completed flight has the wrong landing pose")
            if plan != self.flight_plan or cargo.get("reservationId") != 0 \
                    or cargo.get("motionPhase") != "IDLE":
                starts = [e for e in native if e.get("event") == "MOTION_STARTED"]
                require(len(starts) == 1 and starts[0].get("reason") == "OK"
                        and starts[0]["sequence"] > returned[0]["sequence"]
                        and starts[0].get("valueA") == plan["kind"]
                        and starts[0].get("valueB") == plan["duration"]
                        and motion["phase"] == cargo.get("motionPhase") == "MOVING"
                        and motion["elapsed"] == cargo.get("motionElapsed") == 0
                        and motion["commitPublished"] == motion["commitSequence"] == 0
                        and cargo.get("reservationId") == plan["reservationId"] > 0
                        and plan["reservationId"] != self.flight_reservation
                        and plan["fieldEpoch"] == handle["fieldEpoch"]
                        and plan["origin"] == self.flight_plan["target"]
                            == [cargo["origin"]["x"], cargo["origin"]["y"]]
                        and plan["target"] == [cargo["target"]["x"], cargo["target"]["y"]]
                        and plan["startBaseY"] == self.flight_plan["targetBaseY"]
                        and plan["duration"] == cargo.get("motionDuration")
                        and cargo.get("motionKind") == {1:"WALK", 2:"HOP", 3:"TELEPORT",
                            4:"SKID", 5:"REPOSITION", 6:"FLY_IN"}.get(plan["kind"]),
                        "Throw successor motion preceded exact flight control return")
            else:
                require(cargo.get("motionKind") == "NONE"
                        and cargo.get("origin") == dict(zip(("x", "y"), self.flight_origin))
                        and cargo.get("target") == dict(zip(("x", "y"), PLAYER_TILE))
                        and cargo.get("motionElapsed") == cargo.get("motionDuration") == self.flight_duration
                        and motion["elapsed"] == self.flight_duration
                        and motion["commitPublished"] == motion["commitSequence"] == 1,
                        "Throw landing is not the completed first flight")
            self.flight_terminal.update(returnFrame=sample["frame"], returnActorFrame=clock,
                finishEventSequence=finished[0]["sequence"], controlEventSequence=returned[0]["sequence"])
            self.landed = True
            return
        require(motion["plan"] == self.flight_plan,
                "Throw flight changed source or target before exact control return")
        if self.flight_terminal is None:
            require(motion["phase"] == cargo.get("motionPhase") in ("MOVING", "COMMIT_PENDING")
                    and motion["elapsed"] == cargo.get("motionElapsed")
                    and motion["commitPublished"] == motion["commitSequence"] == 0
                    and cargo.get("commitSequence") == self.flight_commit
                    and cargo.get("reservationId") == self.flight_reservation,
                    "Throw flight changed its original motion owner before terminal commit")
        else:
            require(cargo.get("commitSequence") == self.flight_terminal["commitSequence"]
                    and cargo.get("reservationId") == 0 and cargo.get("motionKind") == "NONE"
                    and cargo.get("motionPhase") == motion["phase"] == "SETTLING"
                    and motion["elapsed"] == self.flight_duration
                    and motion["commitPublished"] == motion["commitSequence"] == 1
                    and cargo.get("logical") == dict(zip(("x", "y"), PLAYER_TILE)),
                    "Throw flight changed its committed settling owner")

    def _sample(self, sample, action, events):
        self._boundary(sample)
        source = self._actor(sample, "geodude")
        target = self._actor(sample, "bellsprout")
        self._rider(sample)
        if action == "launch-natural-throw":
            self.launch_frames += 1
            require(self.launch_frames <= LAUNCH_LIMIT,
                    "natural Throw did not launch within its frame limit")
            if (target.get("motionKind") == "HOP"
                    and source.get("matchedLayerMask", 0) & THROW_RELEASE_BIT):
                require(self.launch_frame is None
                        and target.get("motionPhase") == "MOVING"
                        and source.get("matchedLayerMask", 0) & THROW_RELEASE_BIT,
                        "Bellsprout Hop is not Geodude's active Throw launch")
                origin = target.get("origin", {})
                landing = target.get("target", {})
                carrier = source.get("logical", {})
                carrier_pose = source.get("engineObject", {})
                require((origin.get("x"), origin.get("y"))
                        == (carrier.get("x"), carrier.get("y"))
                        and origin.get("x") == 585
                        and type(origin.get("y")) is int
                        and 0 < PLAYER_TILE[1] - origin["y"] <= THROW_MAX_RANGE
                        and (carrier_pose.get("x"), carrier_pose.get("y"))
                            == (origin["x"], origin["y"])
                        and (carrier_pose.get("pos_x"), carrier_pose.get("pos_z"))
                            == ((origin["x"] << 16) + 0x8000,
                                (origin["y"] << 16) + 0x8000)
                        and (landing.get("x"), landing.get("y")) == PLAYER_TILE
                        and type(target.get("motionDuration")) is int
                        and target["motionDuration"] > 1
                        and target.get("motionElapsed") == 0
                        and type(target.get("reservationId")) is int
                        and target["reservationId"] > 0
                        and type(target.get("commitSequence")) is int
                        and target["commitSequence"] >= 0,
                        "thrown actor did not launch from Geodude toward the player")
                self.flight_origin = (origin["x"], origin["y"])
                self.flight_duration = target["motionDuration"]
                self.flight_reservation = target["reservationId"]
                self.flight_commit = target["commitSequence"]
                motion = self._cargo_motion(sample, target)
                plan = motion["plan"]
                require(plan["version"] == 1 and plan["kind"] == 2
                        and plan["fieldEpoch"] == target["handle"]["fieldEpoch"]
                        and plan["origin"] == list(self.flight_origin)
                        and plan["target"] == list(PLAYER_TILE)
                        and plan["duration"] == self.flight_duration
                        and plan["reservationId"] == self.flight_reservation
                        and plan["startBaseY"] == target["engineObject"].get("pos_y")
                        and motion["phase"] == "MOVING" and motion["elapsed"] == 0
                        and motion["commitPublished"] == motion["commitSequence"] == 0,
                        "Throw launch plan differs from its current full Cargo")
                self.flight_plan = deepcopy(plan)
                self.launch_frame = sample["frame"]
        else:
            self.cross_frames += 1
            require(self.cross_frames <= CROSS_FRAMES,
                    "Throw crossing has more frames than declared")
            if not self.landed:
                motion = self._cargo_motion(sample, target)
                self._terminal(sample, target, events, motion)
            if target.get("motionKind") == "HOP" and not self.landed:
                require((target.get("origin", {}).get("x"),
                         target.get("origin", {}).get("y")) == self.flight_origin
                        and (target.get("target", {}).get("x"),
                             target.get("target", {}).get("y")) == PLAYER_TILE
                        and target.get("motionDuration") == self.flight_duration
                        and target.get("reservationId") == self.flight_reservation
                        and target.get("commitSequence") == self.flight_commit,
                        "Throw flight changed source or target")
                elapsed, duration = target.get("motionElapsed"), target.get("motionDuration")
                if type(elapsed) is int and type(duration) is int \
                        and 0 < elapsed < duration \
                        and target.get("motionPhase") == "MOVING":
                    self.flight_frames += 1
                    pose = target.get("engineObject", {})
                    projectile_z = pose.get("pos_z")
                    player_z = sample["player"]["pos_z"]
                    rider_front = player_z + sample["player"]["face_z"] - HALF_TILE
                    require(type(projectile_z) is int
                            and projectile_z < rider_front,
                            "airborne Bellsprout reached the mounted rider box")
                    if self.previous_projectile_z is not None \
                            and self.previous_projectile_z < player_z - HALF_TILE \
                            <= projectile_z and pose.get("unk88_y", 0) > 0:
                        self.old_box_crossed = True
                    self.previous_projectile_z = projectile_z
                    render = target.get("render", {})
                    if render.get("x") == 585 \
                            and self.flight_origin[1] < render.get("y", -1) < 407:
                        self.travel_seen = True
        self.latest = deepcopy(sample)
        self.observed_frames += 1

    def observe_record(self, row, on_sample=None):
        try:
            require(isinstance(row, dict), "Throw proof row is missing")
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase") == "setup",
                        "Throw initial boundary is misplaced")
                self._boundary(row["initialSnapshot"], fixture=False)
                self.latest = deepcopy(row["initialSnapshot"])
                return self.result()
            require(self.latest is not None, "Throw initial boundary is missing")
            if row.get("phase") == "setup":
                require(self.setup_index < len(SETUP)
                        and row.get("action") == SETUP[self.setup_index],
                        "Throw setup order differs")
                if self.setup_index == 7:
                    require("command" not in row, "Trigger capture is not normal completed frames")
                    for sample, _, _ in validate_raw_chunk(row, self.latest):
                        require(self.trigger_frame is None, "Trigger capture ran past its first ready boundary")
                        self.trigger_frames += 1
                        require(self.trigger_frames <= TRIGGER_LIMIT, "Trigger capture exceeded60 frames")
                        if self._trigger(sample):
                            self.trigger_frame = sample["frame"]
                        self.latest = deepcopy(sample)
                        if on_sample is not None:
                            on_sample(sample, self.observed_frames)
                    if self.trigger_frame is not None:
                        self.setup_index += 1
                    return self.result()
                if self.setup_index == 3:
                    require("command" not in row, "mount settle is not a completed frame stream")
                    for sample, _, _ in validate_raw_chunk(row, self.latest):
                        self._boundary(sample)
                        self.latest = deepcopy(sample)
                        self.settle_frames += 1
                    require(self.settle_frames <= 16, "mount settle exceeded 16 frames")
                    if self.settle_frames == 16:
                        self.setup_index += 1
                    return self.result()
                command = row.get("command")
                require(command == ("teleport", "party", "spawn", None, "bind",
                                    "spawn", "bind", None, "spawn", "bind")
                        [self.setup_index], "Throw setup command differs")
                snapshot = row["snapshot"]
                self._boundary(snapshot)
                require(snapshot["frame"] >= self.latest["frame"],
                        "Throw setup clock reversed")
                if command == "spawn":
                    result = row.get("receipt", {}).get("value", {})
                    if self.setup_index in (5, 8):
                        require(result.get("species") == (74 if self.setup_index == 5 else 69)
                                and type(result.get("slot")) is int
                                and type(result.get("personality")) is int,
                                "Throw native spawn identity differs")
                if command == "bind":
                    subject_id = {4: "cyndaquil", 6: "geodude", 9: "bellsprout"}[self.setup_index]
                    self.subjects[subject_id] = deepcopy(row["receipt"])
                    actor = self._actor(snapshot, subject_id)
                    if subject_id == "bellsprout":
                        require((actor.get("logical", {}).get("x"),
                                 actor.get("logical", {}).get("y")) == TARGET_START,
                                "Bellsprout left its prepared tile")
                    elif subject_id == "geodude":
                        require(actor.get("logical", {}).get("x") == SOURCE_START[0]
                                and 400 <= actor.get("logical", {}).get("y", -1) <= 404,
                                "Geodude differs from its prepared approach line")
                if self.setup_index >= 4:
                    self._rider(snapshot)
                self.latest = deepcopy(snapshot)
                self.setup_index += 1
                return self.result()
            require(self.setup_index == len(SETUP)
                    and row.get("phase") == "observe"
                    and self.action_index < len(ORDER),
                    "Throw observation started before setup or has extra rows")
            action = ORDER[self.action_index]
            require(row.get("action") == action,
                    "Throw action order differs")
            if action in ("launch-natural-throw", "cross-player"):
                require("command" not in row,
                        "Throw step is not a native completed-frame stream")
                for sample, events, _ in validate_raw_chunk(row, self.latest):
                    require(self.launch_frame is None
                            or action != "launch-natural-throw",
                            "Throw launch action ran past its first flight frame")
                    self._sample(sample, action, events)
                    if on_sample is not None:
                        on_sample(sample, self.observed_frames)
                if action == "launch-natural-throw":
                    if self.launch_frame is not None:
                        self.action_index += 1
                elif self.cross_frames == CROSS_FRAMES:
                    self.action_index += 1
                return self.result()
            require(row.get("command") == "player-health.observe",
                    "Throw action is not a checked player HP read")
            snapshot = row.get("snapshot")
            require(isinstance(snapshot, dict),
                    "Throw HP read has no current snapshot")
            self._same_boundary(snapshot)
            self._health(row, action)
            self.latest = deepcopy(snapshot)
            self.action_index += 1
        except (KeyError, TypeError, ValueError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def result(self):
        ready = not self.failures and self.action_index == len(ORDER) \
            and self.launch_frame is not None and self.cross_frames == CROSS_FRAMES \
            and self.landed and self.travel_seen and self.old_box_crossed \
            and self.flight_frames > 0 and self.mount_seat_restored
        return {"ready": ready, "observedFrames": self.observed_frames,
                "observedFrameUnit": "completed-game-frame",
                "failures": list(self.failures),
                "launchFrame": self.launch_frame,
                "triggerFrame": self.trigger_frame,
                "flightFrames": self.flight_frames,
                "oldBoxCrossed": self.old_box_crossed,
                "landed": self.landed,
                "flightTerminal": deepcopy(self.flight_terminal),
                "hpAfterThrow": self.receipts.get("after-contact", {}).get("hp"),
                "mountHitFrame": self.mount_hit_frame,
                "mountKnockback": deepcopy(self.mount_knockback),
                "mountSeatRestored": self.mount_seat_restored,
                "subjects": deepcopy(self.subjects)}

    def stage(self, name):
        require(name in ("launched", "trigger-bound"), "unknown Player HP Throw stage")
        return not self.failures and (self.launch_frame is not None if name == "launched" else self.trigger_frame is not None)

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("Throw proof ended before a complete flight and HP read")
        return {"passed": self.result()["ready"], "failures": list(self.failures)}
