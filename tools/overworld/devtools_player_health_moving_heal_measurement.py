"""One shared moving-heal check for on-foot and mounted Player roles.

Prepared setup is audited and excluded. Existing HP reads name the eligible
health clock; dense native poses prove travel. No guest memory is written.
"""
from copy import deepcopy

from tools.overworld.devtools_player_health_hop_contact_measurement import _inside_swept_body
from tools.overworld.devtools_profile_feature_measurement import application_index
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor


FOOT = "player-health-moving-heal-on-foot-v1"
MOUNTED = "player-health-moving-heal-mounted-v1"
KINDS = (FOOT, MOUNTED)
MODES = {FOOT: "on-foot", MOUNTED: "mounted"}


def setup(mode):
    role = "follower" if mode == "on-foot" else "mounted"
    steps = [("ambush-tile", "teleport", dict(map=33, x=585, z=407, facing=1)),
             ("prepare-cyndaquil", "party", dict(slot=0, species=155, level=50)),
             ("create-"+role, "spawn", dict(species=155, form=0, role=role, slot=0, level=50))]
    if mode == "mounted":
        steps += [("settle-mount", "step", dict(frames=16, keys=[])),
                  ("bind-cyndaquil", "bind", dict(subject="cyndaquil"))]
    steps += [("spawn-passive-"+str(s), "spawn", dict(species=s, form=0, role="wild", level=10, x=582, z=401+i))
              for i,s in enumerate((69,43,44,45,182))]
    return tuple(steps + [("spawn-weepinbell", "spawn", dict(species=70, form=0, role="wild", level=5, x=585, z=402)),
                          ("bind-weepinbell", "bind", dict(subject="weepinbell"))])


def subjects(mode):
    return [("weepinbell",70,"WILD","spawn")] + ([("cyndaquil",155,"MOUNTED","existing")] if mode=="mounted" else [])


def actions():
    rows = [("before-contact", "player-health.observe", {}),
            ("wait-contact", "step", dict(frames=300, keys=["UP"], until=dict(kind="measurement-stage", measurement=None, stage="contact-crossed", when="final"))),
            ("at-contact", "player-health.observe", {}),
            ("move-escape-north", "step", dict(frames=20, keys=["UP","B"])),
            ("move-escape-east", "step", dict(frames=64, keys=["RIGHT","B"]))]
    rows += [("move-delay-loop-"+str(i), "step", dict(frames=16, keys=["LEFT" if i%2==0 else "RIGHT","B"])) for i in range(13)]
    rows += [("move-delay-last", "step", dict(frames=8, keys=["LEFT","B"])),
             ("after-delay", "player-health.observe", {}),
             ("move-first-five", "step", dict(frames=5, keys=["LEFT","B"])),
             ("before-first-heal", "player-health.observe", {}),
             ("move-first-one", "step", dict(frames=1, keys=["LEFT","B"])),
             ("first-heal", "player-health.observe", {})]
    rows += [("move-heal-"+str(i), "step", dict(frames=18, keys=["RIGHT" if i%2==0 else "LEFT","B"])) for i in range(3)]
    return tuple(rows + [("after-one-second", "player-health.observe", {})])


def action_spec(kind):
    rows=deepcopy(actions());rows[1][2]["until"]["measurement"]=kind
    return rows


def validate_recipe(test):
    kind=test["measurements"][0]["kind"];mode=MODES[kind]
    require(test["id"]=="player-hp.moving-heal-"+mode and test["mode"]=="prepared"
            and test["requirements"]==[REQUIREMENT]
            and test["subjects"]==[dict(id=n,species=s,role=r,acquire=a) for n,s,r,a in subjects(mode)]
            and test["measurements"]==[dict(kind=kind,subject="weepinbell")]
            and tuple((a["id"],a["op"],a["args"]) for a in test["setup"])==setup(mode)
            and tuple((a["id"],a["op"],a["args"]) for a in test["actions"])==action_spec(kind)
            and test["assertions"]==[dict(kind="measurement-complete",measurement=kind,when="final")]
            and test["budgets"]["maxFrames"]<=1300 and test["budgets"]["minObservedFrames"]==361,
            "moving-heal fixture or bounded normal input differs")
REQUIREMENT = "current.player-health-moving-heal"
WAIT_LIMIT = 300
AMBUSH_BIT = 1 << application_index("apply-ambush")
# Independent user contract: five damage-free eligible seconds, then 10 HP/s.
# The lastHealthFrame reader is the eligible HP-owner sequence, NOT Actor time.
CHECKPOINTS = (("after-delay", 300, 80, 300, 0),
               ("before-first-heal", 305, 80, 300, 50),
               ("first-heal", 306, 81, 300, 0),
               ("after-one-second", 360, 90, 300, 0))


def require(value, message):
    if not value:
        raise ValueError(message)


def body(pose):
    keys = ("pos_x", "pos_y", "pos_z", "face_x", "face_y", "face_z", "unk88_y")
    require(all(type(pose.get(k)) is int for k in keys), "heal proof has no native body pose")
    return {"pos_x": pose["pos_x"] + pose["face_x"],
            "pos_y": pose["pos_y"] + pose["face_y"] + pose["unk88_y"],
            "pos_z": pose["pos_z"] + pose["face_z"],
            "face_x": 0, "face_y": 0, "face_z": 0}


class PlayerHealthMovingHealMeasurement:
    def __init__(self, source, mode):
        require(mode in ("on-foot", "mounted"), "unknown moving-heal role")
        self.source, self.mode = deepcopy(source), mode
        self.latest = self.context = self.field = self.attacker = self.mount = None
        self.baseline = self.contact = self.crossing = None
        self.wait_frames = self.observed_frames = self.after_hit_frames = 0
        self.checkpoint_index = 0
        self.moving = {"delay": 0, "first-heal": 0, "one-second": 0}
        self.tiles = {k: set() for k in self.moving}
        self.readings, self.failures = {}, []
        self.setup_index = self.setup_frames = self.action_index = self.action_frames = 0
        self.bound = {}

    def _boundary(self, sample):
        require(isinstance(sample, dict) and sample.get("fieldAvailable") is True
                and sample.get("observationBoundary") == "main-task-queue-completion"
                and type(sample.get("frame")) is int and type(sample.get("nativeCycle")) is int
                and sample.get("romSha256") == self.source["romSha256"]
                and sample.get("context", {}).get("mapId") == 33
                and sample.get("fieldControl", {}).get("taskPointer") == 0
                and sample.get("dialogue", {}).get("known") is True
                and sample["dialogue"].get("state") == "idle",
                "moving-heal left the completed eligible field fixture")
        if self.context is not None:
            require(sample["context"] == self.context
                    and sample["fieldControl"].get("fieldPointer") == self.field,
                    "moving-heal field owner or generation changed")
        body(sample.get("player", {}))

    def _actor(self, sample, subject):
        selected = select_current_actor(sample, subject)
        return next(a for a in sample["actors"] if a.get("handle") == selected["handle"])

    def _role(self, sample):
        mounted = [a for a in sample.get("actors", []) if a.get("active") is True and a.get("role") == "MOUNTED"]
        if self.mode == "on-foot":
            require(not mounted, "on-foot healing has a mounted actor")
            return sample["player"]
        require(len(mounted) == 1 and self.mount is not None, "moving-heal mount is absent")
        actor = self._actor(sample, self.mount)
        require(actor.get("role") == "MOUNTED" and actor.get("species") == 155
                and actor.get("inputOwnership") == 1
                and actor.get("engineIdentity", {}).get("anchorInCurrentManager") is True,
                "moving-heal mounted input/anchor identity differs")
        player, pose = sample["player"], actor.get("engineObject", {})
        body(pose)
        require(player["pos_x"] == pose["pos_x"] and player["pos_z"] == pose["pos_z"],
                "moving-heal rider and mount split their native anchor")
        return pose

    def _health(self, row):
        snapshot = row.get("snapshot")
        self._boundary(snapshot)
        self._role(snapshot)
        require(all(snapshot.get(k) == self.latest.get(k) for k in (
            "frame", "nativeCycle", "context", "fieldControl", "player", "actors")),
            "moving-heal HP read is not the latest completed boundary")
        hp = row.get("receipt", {}).get("playerHealth", {})
        identity = hp.get("identity", {})
        require(hp.get("schemaVersion") == 1 and identity.get("descriptorVersion") == 1
                and identity.get("overlayId") == 161
                and identity.get("romSha256") == self.source["romSha256"]
                and identity.get("overlaySha256") == self.source["overlaySha256"]
                and hp.get("frame") == snapshot["frame"]
                and hp.get("nativeCycle") == snapshot["nativeCycle"]
                and hp.get("fieldSystem") == self.field and hp.get("context") == self.context
                and hp.get("maxHp") == 100 and hp.get("hp") == hp.get("savedHp")
                and hp.get("frameActive") is False and hp.get("recoveryPending") is False
                and hp.get("pause", {}).get("fieldTaskActive") is False
                and type(hp.get("lastHealthFrame")) is int
                and hp["lastHealthFrame"] > 0,
                "moving-heal HP/save/owner/clock identity differs")
        if self.baseline is not None:
            require(hp.get("economy") == self.baseline.get("economy")
                    and hp.get("checkpointSpawn") == self.baseline.get("checkpointSpawn"),
                    "moving-heal changed economy or healing checkpoint")
        return deepcopy(hp)

    def arm(self, row, attacker, mount=None):
        require(self.baseline is None and row.get("phase") == "observe"
                and row.get("action") == "before-contact"
                and row.get("command") == "player-health.observe",
                "moving-heal baseline is not the checked pre-contact read")
        self.latest = deepcopy(row["snapshot"])
        self.context = deepcopy(self.latest.get("context"))
        self.field = self.latest.get("fieldControl", {}).get("fieldPointer")
        require(type(self.field) is int and self.field > 0, "moving-heal current Field is missing")
        self.attacker, self.mount = deepcopy(attacker), deepcopy(mount)
        actor = self._actor(self.latest, self.attacker)
        require(actor.get("species") == 70 and actor.get("role") == "WILD",
                "moving-heal source is not the bound Wild Weepinbell")
        self.baseline = self._health(row)
        require((self.baseline["hp"], self.baseline["lastDamage"], self.baseline["acceptedHits"]) == (100, 0, 0),
                "moving-heal starts without natural full player HP")
        return self.result()

    def _crossing(self, sample, cache):
        current = self._actor(sample, self.attacker)
        previous = self._actor(self.latest, self.attacker)
        if current.get("motionKind") != "HOP" or current.get("motionPhase") != "MOVING":
            return
        if not current.get("matchedLayerMask", 0) & AMBUSH_BIT:
            return
        require(isinstance(cache, dict) and cache.get("frame", -1) >= sample["frame"]
                and cache.get("nativeCycle", -1) >= sample["nativeCycle"]
                and current.get("behaviorFingerprint") in sample.get("nativeObservation", {}).get("profileFingerprints", []),
                "moving-heal contact has no current native profile cache")
        profiles = [p for p in cache.get("resolvedProfiles", []) if p.get("resolved") is True
                    and p.get("fingerprint") == current.get("behaviorFingerprint")]
        require(len(profiles) == 1 and profiles[0].get("sourceSha256") == self.source["profileSha256"],
                "moving-heal attack profile source differs")
        profile = bytes.fromhex(profiles[0].get("resultHex", ""))
        require(len(profile) == 216 and tuple(profile[72:75]) == (1, 16, 20)
                and profile[79] == 6 and profiles[0].get("appliedOverrides") == current["matchedLayerMask"],
                "moving-heal source lacks the authored attacking Ambush profile")
        start, end = body(previous["engineObject"]), body(current["engineObject"])
        speed = max(abs(end[k]-start[k]) for k in ("pos_x", "pos_z")) >> 8
        target = body(self._role(self.latest))
        if speed >= 16 and _inside_swept_body(start, end, target):
            self.crossing = {"frame": sample["frame"], "speed": speed,
                             "handle": deepcopy(current["handle"]),
                             "fingerprint": current["behaviorFingerprint"]}

    def _moving(self, sample):
        self.after_hit_frames += 1
        require(self.after_hit_frames <= 360, "moving-heal exceeded its exact eligible window")
        previous, player = self.latest["player"], sample["player"]
        moved = (player["pos_x"], player["pos_z"]) != (previous["pos_x"], previous["pos_z"])
        if self.mode == "mounted":
            actor = self._actor(sample, self.mount)
            ordinary = actor.get("motionKind") in ("WALK", "SKID") and actor.get("motionPhase") in ("MOVING", "COMMIT_PENDING")
        else:
            ordinary = type(player.get("movement_cmd")) is int and player["movement_cmd"] not in (0, 1, 2, 3, 62, 255)
        windows = ["delay"] if self.after_hit_frames <= 300 else ["one-second"]
        if 301 <= self.after_hit_frames <= 306:
            windows.append("first-heal")
        if moved and ordinary:
            for window in windows:
                self.moving[window] += 1
                if player["pos_x"] & 0xFFFF == player["pos_z"] & 0xFFFF == 0x8000:
                    self.tiles[window].add((player["pos_x"] >> 16, player["pos_z"] >> 16))

    def _setup(self, row, on_sample):
        spec=setup(self.mode)
        require(self.setup_index<len(spec) and row.get("action")==spec[self.setup_index][0], "moving-heal setup order differs")
        _,op,args=spec[self.setup_index]
        if op=="step":
            require("command" not in row, "moving-heal mount settle is not normal input")
            for sample,_,_ in validate_raw_chunk(row,self.latest):
                self._setup_boundary(sample);self.latest=deepcopy(sample)
                if on_sample:on_sample(sample,self.observed_frames)
            self.setup_frames+=row["completedGameFrames"]
            require(self.setup_frames<=16,"moving-heal mount settle exceeded16frames")
            if self.setup_frames<16:return
        else:
            require(row.get("command")==op,"moving-heal setup command differs")
            sample=row["snapshot"];self._setup_boundary(sample)
            if op in ("teleport","party","spawn"):
                require(row.get("receipt",{}).get("preparedOnly") is True,"moving-heal setup has no checked preparation receipt")
            if op=="teleport":
                require((sample["player"]["x"],sample["player"]["y"])==(585,407),"moving-heal prepared Player tile differs")
            if op=="bind":
                name=args["subject"];selected=select_current_actor(sample,row["receipt"])
                require((selected["species"],selected["role"])==((155,"MOUNTED") if name=="cyndaquil" else (70,"WILD")),"moving-heal bound role or species differs")
                self.bound[name]=deepcopy(row["receipt"])
            self.latest=deepcopy(sample)
        self.setup_index+=1

    def _setup_boundary(self,sample):
        require(isinstance(sample,dict) and sample.get("fieldAvailable") is True
                and sample.get("observationBoundary")=="main-task-queue-completion"
                and sample.get("romSha256")==self.source["romSha256"],"moving-heal setup has no completed current-ROM boundary")

    def observe_record(self, row, on_sample=None):
        try:
            if "initialSnapshot" in row:
                require(self.latest is None and row.get("phase")=="setup","moving-heal initial boundary is misplaced")
                self._setup_boundary(row["initialSnapshot"]);self.latest=deepcopy(row["initialSnapshot"])
                return self.result()
            if row.get("phase")=="setup":
                self._setup(row,on_sample);return self.result()
            require(row.get("phase")=="observe","moving-heal observation phase differs")
            if self.baseline is None:
                require(self.setup_index==len(setup(self.mode)),"moving-heal setup is incomplete")
                self.arm(row,self.bound["weepinbell"],self.bound.get("cyndaquil"))
                self.action_index=1
                return self.result()
            spec=actions()
            require(self.action_index<len(spec) and row.get("action")==spec[self.action_index][0],"moving-heal action order differs")
            if "command" in row:
                require(row.get("command") == "player-health.observe", "moving-heal forbids setup or writes after arm")
                hp = self._health(row)
                if self.contact is None:
                    require(row.get("action") == "at-contact" and self.crossing is not None
                            and self.crossing["frame"] == self.latest["frame"]
                            and (hp["hp"], hp["acceptedHits"], hp["lastDamage"]) == (80, 1, 20)
                            and hp.get("restFrames") == hp.get("healRemainder") == 0
                            and hp.get("hitThisFrame") is True and hp.get("protectionFrames") == 60,
                            "moving-heal lacks one real hit at the exact contact boundary")
                    self.contact = hp
                    self.readings["at-contact"] = hp
                else:
                    require(self.checkpoint_index < len(CHECKPOINTS), "moving-heal has extra HP reads")
                    action, eligible, value, wait, remainder = CHECKPOINTS[self.checkpoint_index]
                    require(row.get("action") == action and self.after_hit_frames == eligible
                            and hp["lastHealthFrame"]-self.contact["lastHealthFrame"] == eligible
                            and hp["frame"]-self.contact["frame"] == eligible
                            and hp.get("pause", {}).get("healthClockPaused") is False,
                            "moving-heal eligible HP clock skipped or included paused frames")
                    require((hp["hp"], hp["restFrames"], hp["healRemainder"]) == (value, wait, remainder)
                            and (hp["acceptedHits"], hp["lastDamage"]) == (1, 20)
                            and hp.get("protectionFrames") == 0 and hp.get("hitThisFrame") is False,
                            "moving-heal delay, rate, remainder or accepted-hit count differs")
                    self.readings[action] = hp
                    self.checkpoint_index += 1
                self.action_index+=1
                return self.result()
            require(row.get("action") == "wait-contact" if self.contact is None
                    else row.get("action", "").startswith("move-"), "moving-heal action differs")
            for sample, _, _ in validate_raw_chunk(row, self.latest):
                self._boundary(sample)
                self._role(sample)
                if self.contact is None:
                    self.wait_frames += 1
                    require(self.wait_frames <= WAIT_LIMIT and self.crossing is None,
                            "moving-heal passed its first collision or wait limit")
                    self._crossing(sample, row.get("profileCache"))
                else:
                    self._moving(sample)
                self.latest = deepcopy(sample)
                self.observed_frames += 1
                self.action_frames += 1
                require(self.action_frames<=spec[self.action_index][2]["frames"],"moving-heal action frame bound differs")
                if on_sample is not None:
                    on_sample(sample, self.observed_frames)
            if self.contact is None:
                if self.crossing is not None:self.action_index+=1;self.action_frames=0
            elif self.action_frames==spec[self.action_index][2]["frames"]:
                self.action_index+=1;self.action_frames=0
        except (KeyError, TypeError, ValueError, StopIteration) as error:
            self.failures.append(str(error))
        return self.result()

    def stage(self, name):
        require(name == "contact-crossed", "unknown moving-heal stage")
        return not self.failures and self.crossing is not None and self.contact is None

    def result(self):
        motion = self.moving["delay"] >= 150 and self.moving["first-heal"] >= 3 \
            and self.moving["one-second"] >= 30 and len(self.tiles["delay"]) >= 3 \
            and len(self.tiles["one-second"]) >= 2
        return {"ready": not self.failures and self.checkpoint_index == len(CHECKPOINTS) and self.action_index==len(actions()) and motion,
                "kind": FOOT if self.mode=="on-foot" else MOUNTED, "acceptedProof":False,
                "subjects":deepcopy(self.bound),
                "observedFrames": self.observed_frames, "observedFrameUnit": "completed-game-frame",
                "failures": list(self.failures), "mode": self.mode,
                "crossing": deepcopy(self.crossing), "movingFrames": dict(self.moving),
                "movingTiles": {k: len(v) for k, v in self.tiles.items()},
                "eligibleHealthFrames": (self.readings.get("after-one-second", {}).get("lastHealthFrame", 0)
                                         - self.contact["lastHealthFrame"] if "after-one-second" in self.readings else None),
                "rawFramesAfterHit": self.after_hit_frames,
                "hpAfter": self.readings.get("after-one-second", {}).get("hp")}

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("moving-heal ended without delay, +10 HP and real role-matched movement")
        return {"passed": self.result()["ready"], "failures": list(self.failures)}
