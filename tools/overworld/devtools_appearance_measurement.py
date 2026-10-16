"""Replay of real HP, palette upload and material-use receipts; no emulator."""
from copy import deepcopy
import json
import struct
import time

from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.devtools_profile_feature_measurement import application_index
from tools.overworld.devtools_movement_predicates import player_settled_at

RAM = application_index("apply-ram")
AMBUSH = application_index("apply-ambush")

DAMAGE = "pokemon-damage-palette-v1"
COOLDOWN = "pokemon-cooldown-palette-v1"
AMBUSH_COOLDOWN = "pokemon-ambush-cooldown-palette-v1"
KINDS = (DAMAGE, COOLDOWN, AMBUSH_COOLDOWN)
CONFIG = {
    DAMAGE: dict(id="pokemon-appearance.damage-palette", requirement="current.pokemon-damage-palette",
        subjects=(("cyndaquil",155,"MOUNTED","existing"), ("snorlax",143,"WILD","spawn"),
                  ("weepinbell",70,"WILD","spawn"), ("healed-cyndaquil",155,"FOLLOWER","existing")), minimum=60),
    AMBUSH_COOLDOWN: dict(id="pokemon-appearance.ambush-cooldown-palette",
        requirement="current.pokemon-ambush-cooldown-palette",
        subjects=(("weepinbell",70,"WILD","spawn"),), minimum=90),
    COOLDOWN: dict(id="pokemon-appearance.cooldown-palette", requirement="current.pokemon-cooldown-palette",
        subjects=(("onix",95,"WILD","spawn"),), minimum=1),
}


def need(ok, reason):
    if not ok:
        raise ValueError("appearance proof: " + reason)


def same_line_boundary(left, right):
    # Dense samples omit repeated resolver/terrain diagnostics. The path
    # receipt checks its terrain separately. Every game field remains exact.
    left, right = deepcopy(left), deepcopy(right)
    if "terrain" not in left or "terrain" not in right:
        for boundary in (left, right):
            boundary.pop("terrain", None)
    if "resolvedProfiles" not in left["nativeObservation"] or "resolvedProfiles" not in right["nativeObservation"]:
        for boundary in (left, right):
            boundary["nativeObservation"].pop("resolvedProfiles", None)
    return left == right


def _current(view, actor):
    need(view["handle"] == actor["handle"] and all(view[k] == actor[k] for k in
        ("subjectIdentity", "species", "form", "level", "authorityGeneration", "engineAnchorGeneration", "presentationGeneration"))
        and view["role"] == actor["role"] and view["owner"]["actor"]["handle"] == actor["handle"],
        "palette has a stale full actor identity")


def blend(original, mode, strength):
    need(mode in (1,2) and (0 if mode == 1 else 1) <= strength <= 16
         and len(original) % 32 == 0, "blend inputs differ")
    target = (31,0,0) if mode == 1 else (0,0,31)
    result = bytearray()
    for i, color in enumerate(struct.unpack("<" + "H" * (len(original)//2), original)):
        value = color if i % 16 == 0 else (color & 0x8000) | sum(
            ((((color >> (channel*5)) & 31) * (16-strength) + target[channel]*strength + 8) >> 4)
                << (channel*5) for channel in range(3))
        result.extend(struct.pack("<H",value))
    return bytes(result)


def damage_pulse(hp, max_hp, actor_frame):
    need(type(actor_frame) is int and 0 <= actor_frame <= 0xffffffff,
         "damage pulse lacks the current Actor frame")
    need(type(hp) is int and type(max_hp) is int and 0 <= hp <= max_hp <= 0xffff,
         "damage pulse HP differs")
    if max_hp == 0 or hp >= max_hp:
        return dict(peak=0,period=0,phase=0,strength=0)
    peak = 1 + ((max_hp-hp)*5 + max_hp-1)//max_hp
    shift = 7 - ((peak-2)>>1)
    period = 1 << shift
    phase = actor_frame & (period-1)
    triangle = min(phase,period-phase)
    strength = 0 if triangle <= period//4 else (peak*(triangle-period//4)) >> (shift-2)
    return dict(peak=peak,period=period,phase=phase,strength=strength)


def damage_strength(hp, max_hp, actor_frame):
    return damage_pulse(hp,max_hp,actor_frame)["strength"]


def verify_palette(view, upload, material, actor, mode, strength):
    _current(view, actor)
    need(view["mode"] == mode and view["strength"] == strength and view["yielded"] == 0
         and view["drawCommand"] == 4 and view["drawTiming"] == 2, "tint mode, strength or callback admission differs")
    original, tinted = (bytes.fromhex(view[k]) for k in ("originalHex","tintedHex"))
    need(len(original) == len(tinted) == view["paletteBytes"] and 32 <= len(original) <= 512
         and tinted == blend(original, mode, strength)
         and (tinted == original if strength == 0 else tinted != original),
         "real palette colors do not match the exact HP/cooldown blend")
    for receipt in (upload, material):
        _current(receipt["view"], actor)
        need(all(receipt["view"][k] == view[k] for k in
             ("mode", "strength", "recordPointer", "drawPointer", "modelPointer", "texturePointer",
              "originalPaletteKey", "privatePaletteKey", "originalHex", "tintedHex")),
             "SDK/MAT receipt belongs to another palette update")
    need(upload["completed"] is True and upload["sourcePointer"] == view["tintedPalettePointer"]
         and upload["paletteBytes"] == view["paletteBytes"] and upload["uploadedHex"] == view["tintedHex"]
         and upload["destinationOffset"] == (view["privatePaletteKey"] & 0xffff) << 3
         and 0x06800000 <= upload["destinationAddress"] - upload["destinationOffset"] <= 0x068A0000,
         "real SDK palette upload bytes, destination or completion differ")
    callback=upload.get("callback")
    need(upload.get("dispatch") == "field-vblank" and isinstance(callback,dict)
         and callback.get("callbackAddress") == 0x021E5900
         and callback.get("fieldPointer") == view["owner"]["fieldPointer"],
         "palette upload did not use the current stock Field VBlank callback")
    original_base = (view["originalPaletteKey"] & 0xffff) >> 1
    offset = material["beforeWord"] - original_base
    need(material["textureFormat"] == 3 and 0 <= offset <= (view["paletteBytes"]-32)//16
         and offset % 2 == 0 and material["afterWord"] == (material["beforeWord"] if strength == 0
             else ((view["privatePaletteKey"] & 0xffff)>>1) + offset)
         and material["renderObjectPointer"] == view["drawPointer"] + 0x30
         and material["uploadId"] == upload["uploadId"],
         "real MAT command did not use the normal off-phase or uploaded tint palette")
    return dict(mode=mode,strength=strength,off=strength==0,uploadId=upload["uploadId"],
                privatePaletteKey=view["privatePaletteKey"],
                originalHex=view["originalHex"],tintedHex=view["tintedHex"],
                sourcePointer=upload["sourcePointer"],destinationAddress=upload["destinationAddress"],
                beforeWord=material["beforeWord"],afterWord=material["afterWord"],handle=deepcopy(actor["handle"]))


def rest_eligible(conditions):
    states, frame = conditions["states"], conditions["frame"]
    return bool(states) and any(s["enabled"] for s in states) and all(
        not s["flags"] & 1 and s["flags"] & 2 and s["cooldownFrames"] > 0
        and 0 < ((s["cooldownUntil"]-frame) & 0xffffffff) < 0x80000000 for s in states)


LINE_ACTION = "approach-current-line"
AMBUSH_LINES = ("stage-outside-vision", "approach-ambush")
LINE_FRAMES = 96
LINE_SECONDS = 90










class AppearanceMeasurement:
    def __init__(self, kind, test, source):
        need(kind in KINDS, "measurement kind differs")
        self.kind, self.test, self.source = kind, test, source
        self.latest = None
        self.subjects = {}
        self.observed_frames = 0
        self.failures = []
        self.baseline = {}
        self.previous = {}
        self.hits = {"cyndaquil":[],"snorlax":[]}
        self.palettes = {"cyndaquil":[],"snorlax":[]}
        self.pulse_directions = {"cyndaquil":set(),"snorlax":set()}
        self.previous_palette = {}
        self.upload_events, self.material_events = {}, {}
        self.natural_heal = self.clear = self.blue = self.expired = None
        self.crashes = []
        self.last_blue_conditions = None
        self.setup_index = 0
        self.current_conditions = None
        self.first_activation = self.first_cooldown = None
        self.profile_active = False
        self.profile_cache = None
        self.attack_frames = 0

    def _appearance(self, sample):
        data = sample.get("pokemonAppearance",{})
        need(data.get("schemaVersion") == 1 and data.get("available") is True
             and data.get("frame") == sample["frame"] and data.get("nativeCycle") == sample["nativeCycle"]
             and data.get("observationBoundary") == "main-task-queue-completion"
             and data.get("identity") == {k:self.source[k] for k in
                 ("romSha256","capsuleElfSha256","behaviorBlobSha256")},
             "palette reader has no authenticated current completed frame")
        return data

    def _actor(self, sample, name):
        selected=select_current_actor(sample,self.subjects[name])
        return next(a for a in sample["actors"] if a["handle"]==selected["handle"])

    def _hp(self, sample, actor):
        data=sample.get("pokemonCombat",{})
        need(data.get("available") is True and data.get("frame")==sample["frame"]
             and data.get("nativeCycle")==sample["nativeCycle"]
             and data.get("identity",{}).get("romSha256")==self.source["romSha256"]
             and data.get("identity",{}).get("overlaySha256")==self.source["overlaySha256"], "real Pokémon HP is missing")
        rows=[r for r in data.get("targets",[]) if r.get("handle")==actor["handle"]]
        need(len(rows)==1,"real HP target has a stale identity")
        row=rows[0]
        need(row["personality"]==actor["subjectIdentity"] and row["hp"]==row["currentHp"]
             and 0<row["hp"]<=row["maxHp"]
             and row["hpSource"]==("wild-resident" if actor["role"]=="WILD" else "party"),
             "real living target HP differs")
        if actor["role"] != "WILD":
            party=[m for m in sample["party"] if m["personality"]==row["personality"]]
            need(len(party)==1 and (party[0]["hp"],party[0]["maxHp"])==(row["hp"],row["maxHp"]),"party HP is a shadow value")
        return row

    @staticmethod
    def _forward_line(sample, actor):
        player, object_ = sample["player"], actor["engineObject"]
        dx, dz = player["x"] - object_["x"], player["y"] - object_["y"]
        forward = {0: (dx == 0 and -32 <= dz < 0),
                   1: (dx == 0 and 0 < dz <= 32),
                   2: (dz == 0 and -32 <= dx < 0),
                   3: (dz == 0 and 0 < dx <= 32)}
        return forward.get(object_["facing"], False) \
            and player_settled_at(sample, 33, player["x"], player["y"])

    @staticmethod
    def _slot(mapping, slot):
        return mapping.get(str(slot),mapping.get(slot))

    def _record_events(self, sample, events):
        for event in events:
            data=event.get("data",{})
            if event.get("kind")=="native-observation":
                kind=data.get("observation")
                if kind in ("appearance-sdk-upload-complete","Appearance_ApplyMaterial"):
                    need(event["frame"]==sample["frame"],"palette receipt escaped its completed queue")
                    cache=self.upload_events if kind=="appearance-sdk-upload-complete" else self.material_events
                    cache[data["uploadId"]]=deepcopy(data)
                elif kind=="appearance-native-heal" and self.kind==DAMAGE and "cyndaquil" in self.subjects:
                    if data["subjectIdentity"]==self.subjects["cyndaquil"]["subjectIdentity"]:
                        need(data["mapId"]==69 and data["synthetic"] is False and data["requestedHp"]>0,
                             "healing did not use normal stock party code")
                        self.natural_heal=deepcopy(data)
            elif event.get("kind")=="native" and self.kind==COOLDOWN and "onix" in self.subjects:
                if data.get("event")=="WORLD_EFFECT" and data.get("valueA")==3:
                    actor=self._actor(sample,"onix")
                    if data.get("actorHandle")==actor["handle"]["value"]:
                        need(data.get("actor")=={k:v for k,v in actor["handle"].items() if k!="value"},"Crash owner is stale")
                        self.crashes.append(deepcopy(event))

    def _palette(self, data, actor, mode, strength):
        rows=[r for r in data["records"] if r["handle"]==actor["handle"]]
        if not rows:
            return None
        view=rows[0]
        if view.get("uploadPending"):
            return None # The real stock transfer and a later MAT must finish first.
        slot=actor["handle"]["slot"]
        upload,material=(self._slot(data[k],slot) for k in ("uploads","materials"))
        if upload is None or material is None or material["uploadId"]!=upload["uploadId"]:
            return None # A real later draw, not a fabricated draw, must complete it.
        proof=verify_palette(view,upload,material,actor,mode,strength)
        need(proof["uploadId"] in self.upload_events and proof["uploadId"] in self.material_events,
             "palette caches lack actual SDK/MAT native return receipts")
        verify_palette(view, self.upload_events[proof["uploadId"]],
                       self.material_events[proof["uploadId"]], actor, mode, strength)
        return proof

    def _clear(self,data,actor):
        clear=self._slot(data["clears"],actor["handle"]["slot"])
        if clear is None:
            return None
        draw=clear["draw"]
        need(draw["owner"]["actor"]["handle"]==actor["handle"]
             and all(draw["owner"]["actor"][k]==actor[k] for k in
                 ("subjectIdentity","authorityGeneration","engineAnchorGeneration","presentationGeneration"))
             and not any(r["handle"]==actor["handle"] for r in data["records"])
             and draw["drawCallback"]==0 and draw["drawCommand"]==0 and draw["drawTiming"]==0
             and len(bytes.fromhex(draw["paletteHex"]))==draw["paletteBytes"],
             "full HP/expiry still uses a tinted record or callback")
        return deepcopy(clear)

    def _profile(self, sample, actor):
        cache=self.profile_cache
        need(isinstance(cache,dict) and cache["frame"]>=sample["frame"]
             and cache["nativeCycle"]>=sample["nativeCycle"]
             and actor["behaviorFingerprint"] in sample.get("nativeObservation",{}).get("profileFingerprints",[]),
             "attack lacks a coherent native resolved profile")
        matches=[p for p in cache.get("resolvedProfiles",[]) if p.get("resolved") is True
                 and p.get("fingerprint")==actor["behaviorFingerprint"]]
        need(len(matches)==1 and matches[0]["sourceSha256"]==self.source["profileSha256"]
             and matches[0].get("appliedOverrides",0) & (1<<AMBUSH),
             "attack profile is not the sealed current source")
        data=bytes.fromhex(matches[0]["resultHex"])
        need(len(data)==216 and tuple(data[72:75])==(1,16,20) and data[79]==6,
             "ordinary Ambush damage parameters differ")
        self.attack_frames+=1


    def _own_cooldown(self, sample, data):
        application = AMBUSH if self.kind == AMBUSH_COOLDOWN else RAM
        name = "weepinbell" if self.kind == AMBUSH_COOLDOWN else "onix"
        duration, cooldown = (90, 126) if self.kind == AMBUSH_COOLDOWN else (0, 100)
        actor = self._actor(sample, name); hp = self._hp(sample, actor)
        need(sample["context"]["mapId"] == 33 and hp["hp"] == hp["maxHp"],
             "cooldown palette target lost field or full HP")
        conditions = self._slot(data["conditions"], actor["handle"]["slot"])
        if conditions is None or not conditions.get("available"):
            return
        need(conditions["frame"] == sample["actorFrame"] and all(
             conditions["owner"]["actor"].get(k) == actor.get(k) for k in
             ("handle", "subjectIdentity", "role", "authorityGeneration", "engineAnchorGeneration", "presentationGeneration"))
             and {s["application"] for s in conditions["states"]} == {application},
             "blue lacks the exact entire current own-profile prepared set")
        state = conditions["states"][0]
        need((state["durationFrames"], state["cooldownFrames"]) == (duration, cooldown),
             "own-profile cooldown catalog clocks differ")
        self.current_conditions = deepcopy(conditions)
        active = bool(state["flags"] & 1)
        if active:
            need(actor["matchedLayerMask"] & (1 << application), "active cooldown profile lost its actual application")
            if self.first_activation is None:
                self.first_activation = dict(frame=sample["frame"], actorFrame=conditions["frame"],
                    triggerFrame=(state["activeUntil"]-duration)&0xffffffff if duration else conditions["frame"],
                    state=deepcopy(state))
        if not active and self.profile_active:
            need(state["flags"] & 2 and not actor["matchedLayerMask"] & (1 << application),
                 "cooldown profile did not naturally leave its active application")
            if duration:
                before = self.first_activation["state"]
                need(state["activeUntil"] == before["activeUntil"]
                     and (state["cooldownUntil"]-self.first_activation["triggerFrame"])&0xffffffff == cooldown
                     and (conditions["frame"]-state["activeUntil"])&0xffffffff < 0x80000000,
                     "timed Ambush did not naturally reach its authored deadline")
            else:
                need(self.crashes, "Ram cooldown has no real accepted same-actor Crash")
            if self.first_cooldown is None:
                self.first_cooldown = dict(frame=sample["frame"], actorFrame=conditions["frame"], state=deepcopy(state))
        self.profile_active = active
        if rest_eligible(conditions):
            need(self.first_activation is not None and self.first_cooldown is not None,
                 "blue lacks the real own-profile activation and natural cooldown edge")
            palette = self._palette(data, actor, 2, 2)
            if palette and self.blue is None:
                self.blue = palette; self.last_blue_conditions = deepcopy(conditions)
        elif self.blue is not None and (conditions["frame"]-self.last_blue_conditions["states"][0]["cooldownUntil"])&0xffffffff < 0x80000000:
            self.expired = self._clear(data, actor)


    def _sample(self,sample,events):
        need(sample.get("observationBoundary")=="main-task-queue-completion"
             and sample.get("romSha256")==self.source["romSha256"],"wrong ROM or sample boundary")
        self._record_events(sample,events)
        self.observed_frames+=1
        if sample.get("fieldAvailable") is False:
            need(self.kind==DAMAGE and self.stage("two-red-hits"),"subject field vanished during palette proof")
            return
        data=self._appearance(sample)
        if self.kind == AMBUSH_COOLDOWN:
            self._own_cooldown(sample,data)
        elif self.kind==DAMAGE:
            if "healed-cyndaquil" in self.subjects:
                actor=self._actor(sample,"healed-cyndaquil")
                hp=self._hp(sample,actor)
                need(actor["subjectIdentity"]==self.subjects["cyndaquil"]["subjectIdentity"]
                     and self.natural_heal is not None and hp["hp"]==hp["maxHp"]
                     and self.natural_heal["requestedHp"]==hp["maxHp"],"healed Pokémon is not the same real full-HP party member")
                self.clear=self._clear(data,actor)
                return
            if sample["context"]["mapId"]!=33:
                need(self.stage("two-red-hits"),"left the hit fixture before two palette updates")
                return
            for name in ("cyndaquil","snorlax"):
                actor=self._actor(sample,name)
                hp=self._hp(sample,actor)
                old=self.previous.get(name,hp)
                delta=old["hp"]-hp["hp"]
                if delta:
                    need(delta==20 and hp["hitCount"]==old["hitCount"]+1 and hp["immunityFrames"]>=59,
                         "HP loss lacks one real accepted guarded Ambush hit")
                    attacker=self._actor(sample,"weepinbell")
                    need(attacker["matchedLayerMask"] & (1<<AMBUSH),"hit did not use the actual Ambush profile")
                    self._profile(sample,attacker)
                    self.hits[name].append(dict(frame=sample["frame"],hp=hp["hp"],maxHp=hp["maxHp"],hitCount=hp["hitCount"]))
                if self.hits[name]:
                    pulse=damage_pulse(hp["hp"],hp["maxHp"],sample["actorFrame"])
                    strength=pulse["strength"]
                    palette=self._palette(data,actor,1,strength)
                    if palette:
                        palette.update(frame=sample["frame"],actorFrame=sample["actorFrame"],
                            hp=hp["hp"],maxHp=hp["maxHp"],hitCount=hp["hitCount"],
                            pulsePeak=pulse["peak"],pulsePeriod=pulse["period"],pulsePhase=pulse["phase"])
                        prior=self.previous_palette.get(name)
                        if prior and all(prior[k]==palette[k] for k in
                                ("hp","maxHp","hitCount","privatePaletteKey","handle")):
                            need(0 <= ((palette["actorFrame"]-prior["actorFrame"]) & 0xffffffff)
                                 < 0x80000000,"damage pulse Actor clock reversed")
                            delta=strength-prior["strength"]
                            if delta:
                                self.pulse_directions[name].add(1 if delta>0 else -1)
                        self.previous_palette[name]=deepcopy(palette)
                        if not any((p["strength"],p["hitCount"])==(strength,hp["hitCount"])
                                for p in self.palettes[name]):
                            self.palettes[name].append(palette)
                self.previous[name]=deepcopy(hp)
        else:
            self._own_cooldown(sample, data)

    def observe_record(self,row,on_sample=None):
        try:
            if "initialSnapshot" in row:
                need(self.latest is None,"duplicate initial palette boundary")
                self.latest=deepcopy(row["initialSnapshot"])
                return self.result()
            need(self.latest is not None,"initial palette frame is missing")
            if "samples" in row:
                self.profile_cache=row.get("profileCache")
                for sample,events,_ in validate_raw_chunk(row,self.latest):
                    if row["phase"]=="observe":
                        self._sample(sample,events)
                    self.latest=deepcopy(sample)
                    if on_sample:
                        on_sample(sample,self.observed_frames)
                return self.result()
            snapshot=row.get("snapshot")
            need(isinstance(snapshot,dict),"palette command has no current boundary")
            if row.get("command")=="bind":
                spec=next(a for a in self.test["setup"]+self.test["actions"] if a["id"]==row["action"])
                name=spec["args"]["subject"]
                self.subjects[name]=deepcopy(row["receipt"])
                actor=self._actor(snapshot,name)
                if self.kind == AMBUSH_COOLDOWN:
                    need(actor["logical"] == dict(x=585,y=402) and snapshot["player"]["x"] == 585
                         and snapshot["player"]["y"] == 403 and self._hp(snapshot,actor)["hp"] == self._hp(snapshot,actor)["maxHp"],
                         "Ambush blue fixture did not bind its current healthy native actor")
                if self.kind==COOLDOWN:
                    need(actor["engineObject"]["facing"]==1
                         and actor["logical"]==dict(x=585,y=402)
                         and snapshot["player"]["x"]==585 and snapshot["player"]["y"]==407,
                         "blue fixture did not bind actual South-facing Onix north of player")
                if self.kind==DAMAGE and name in ("cyndaquil","snorlax"):
                    hp=self._hp(snapshot,actor)
                    need(hp["hp"]==hp["maxHp"] and hp["hitCount"]==0,"palette fixture was damaged before its normal trigger")
                    self.baseline[name]=deepcopy(hp)
                    self.previous[name]=deepcopy(hp)
            self.latest=deepcopy(snapshot)
        except (ValueError,KeyError,TypeError,StopIteration) as error:
            self.failures.append(str(error))
        return self.result()


    def stage(self,name):
        if name=="hits-settled":
            if self.kind!=DAMAGE or self.latest is None or not self.stage("two-red-hits"):
                return False
            actor=self._actor(self.latest,"cyndaquil")
            player=self.latest["player"]
            # A hit is queued while the old idle pose can still be visible.
            # Wait for a later completed queue before accepting the ground pose.
            return self.latest["frame"]>self.hits["cyndaquil"][-1]["frame"] \
                and actor["motionPhase"]=="IDLE" and actor["reservationId"]==0 \
                and player_settled_at(self.latest,33,player["x"],player["y"])
        if name=="two-red-hits":
            hit_counts={p["hitCount"] for p in self.palettes["cyndaquil"]}
            return len(self.hits["cyndaquil"])>=2 and len(hit_counts)>=2 \
                and self.pulse_directions["cyndaquil"]=={-1,1} and all(
                    any(p["off"] for p in self.palettes[subject])
                    and any(not p["off"] for p in self.palettes[subject])
                    for subject in ("cyndaquil","snorlax"))
        if name=="blue-used":
            return self.blue is not None
        if name=="attack-started":
            return self.first_activation is not None
        if name=="attack-ended":
            return self.first_cooldown is not None
        if name=="crashed":
            return bool(self.crashes)
        return False

    def finish(self):
        if not self.result()["ready"] and not self.failures:
            self.failures.append("appearance proof: native palette/clear lifecycle is incomplete")
        return self.result()

    def result(self):
        ready=(self.stage("two-red-hits") and self.clear is not None if self.kind==DAMAGE else
               self.blue is not None and self.expired is not None
               and self.first_activation is not None and self.first_cooldown is not None
               and (self.kind==AMBUSH_COOLDOWN or bool(self.crashes)))
        ready=ready and self.observed_frames>=CONFIG[self.kind]["minimum"]
        return dict(kind=self.kind,state="failed" if self.failures else "passed" if ready else "running",
            ready=bool(ready),passed=bool(ready and not self.failures),acceptedProof=False,
            observedFrames=self.observed_frames,failures=deepcopy(self.failures),subjects=deepcopy(self.subjects),
            hits=deepcopy(self.hits),palettes=deepcopy(self.palettes),naturalHeal=deepcopy(self.natural_heal),
            pulseDirections={k:sorted(v) for k,v in self.pulse_directions.items()},
            cleared=deepcopy(self.clear),blue=deepcopy(self.blue),expired=deepcopy(self.expired),
            blueConditions=deepcopy(self.last_blue_conditions),crashes=deepcopy(self.crashes),
            firstActivation=deepcopy(self.first_activation), firstCooldown=deepcopy(self.first_cooldown),
            attackFrames=self.attack_frames)



RECIPE_ACTIONS = json.loads('{"pokemon-damage-palette-v1":{"setup":[{"id":"attack-tile","op":"teleport","args":{"map":33,"x":585,"z":407,"facing":1}},{"id":"prepare-cyndaquil","op":"party","args":{"slot":0,"species":155,"level":50}},{"id":"mount-cyndaquil","op":"spawn","args":{"species":155,"form":0,"role":"mounted","slot":0,"level":50}},{"id":"settle-mount","op":"step","args":{"frames":16,"keys":[]}},{"id":"bind-cyndaquil","op":"bind","args":{"subject":"cyndaquil"}},{"id":"spawn-snorlax","op":"spawn","args":{"species":143,"form":0,"role":"wild","level":50,"x":585,"z":405}},{"id":"bind-snorlax","op":"bind","args":{"subject":"snorlax"}},{"id":"spawn-weepinbell","op":"spawn","args":{"species":70,"form":0,"role":"wild","level":10,"x":585,"z":404}},{"id":"bind-weepinbell","op":"bind","args":{"subject":"weepinbell"}}],"actions":[{"id":"two-real-hits","op":"wait","args":{"predicate":{"kind":"measurement-stage","measurement":"pokemon-damage-palette-v1","stage":"two-red-hits","when":"final"}}},{"id":"settle-last-hit","op":"wait","args":{"predicate":{"kind":"measurement-stage","measurement":"pokemon-damage-palette-v1","stage":"hits-settled","when":"final"}}},{"id":"normal-center","op":"teleport","args":{"map":69,"x":8,"z":13,"facing":0}},{"id":"nurse-idle","op":"wait","args":{"predicate":{"kind":"dialogue-state","state":"idle"}}},{"id":"nurse-start-ready","op":"wait","args":{"predicate":{"kind":"dialogue-state","state":"idle"}}},{"id":"nurse-start-a","op":"step","args":{"frames":16,"keys":["A"],"until":{"kind":"selector-field","path":"newKeys","operator":"eq","value":1}}},{"id":"nurse-start-consumed","op":"wait","args":{"predicate":{"kind":"dialogue-state","state":"printing"}}},{"id":"greeting-page-one-ready","op":"wait","args":{"predicate":{"kind":"dialogue-state","state":"page-wait"}}},{"id":"greeting-page-one-a","op":"step","args":{"frames":16,"keys":["A"],"until":{"kind":"selector-field","path":"newKeys","operator":"eq","value":1}}},{"id":"greeting-page-one-consumed","op":"wait","args":{"predicate":{"kind":"dialogue-state","state":"printing"}}},{"id":"greeting-page-two-ready","op":"wait","args":{"predicate":{"kind":"dialogue-state","state":"page-wait"}}},{"id":"greeting-page-two-a","op":"step","args":{"frames":16,"keys":["A"],"until":{"kind":"selector-field","path":"newKeys","operator":"eq","value":1}}},{"id":"greeting-page-two-consumed","op":"wait","args":{"predicate":{"kind":"dialogue-state","state":"printing"}}},{"id":"nurse-yes-ready","op":"wait","args":{"predicate":{"kind":"dialogue-state","state":"yes-no-ready"}}},{"id":"nurse-yes-a","op":"step","args":{"frames":16,"keys":["A"],"until":{"kind":"selector-field","path":"newKeys","operator":"eq","value":1}}},{"id":"nurse-yes-consumed","op":"wait","args":{"predicate":{"kind":"dialogue-state","state":"busy"}}},{"id":"healed-page-one-ready","op":"wait","args":{"predicate":{"kind":"dialogue-state","state":"page-wait"}}},{"id":"healed-page-one-a","op":"step","args":{"frames":16,"keys":["A"],"until":{"kind":"selector-field","path":"newKeys","operator":"eq","value":1}}},{"id":"healed-page-one-consumed","op":"wait","args":{"predicate":{"kind":"dialogue-state","state":"printing"}}},{"id":"healed-page-two-ready","op":"wait","args":{"predicate":{"kind":"dialogue-state","state":"page-wait"}}},{"id":"healed-page-two-a","op":"step","args":{"frames":16,"keys":["A"],"until":{"kind":"selector-field","path":"newKeys","operator":"eq","value":1}}},{"id":"healed-page-two-consumed","op":"wait","args":{"predicate":{"kind":"dialogue-state","state":"busy"}}},{"id":"nurse-final-ready","op":"wait","args":{"predicate":{"kind":"dialogue-state","state":"script-button-wait"}}},{"id":"nurse-final-a","op":"step","args":{"frames":16,"keys":["A"],"until":{"kind":"selector-field","path":"newKeys","operator":"eq","value":1}}},{"id":"nurse-final-consumed","op":"wait","args":{"predicate":{"kind":"dialogue-state","state":"busy"}}},{"id":"nurse-finished","op":"wait","args":{"predicate":{"kind":"dialogue-state","state":"idle"}}},{"id":"normal-outdoor","op":"teleport","args":{"map":33,"x":585,"z":407,"facing":1}},{"id":"same-party-follower","op":"spawn","args":{"species":155,"form":0,"role":"follower","slot":0,"level":50}},{"id":"bind-healed-cyndaquil","op":"bind","args":{"subject":"healed-cyndaquil"}},{"id":"full-hp-draw","op":"step","args":{"frames":16,"keys":[],"until":{"kind":"measurement-complete","measurement":"pokemon-damage-palette-v1","when":"final"}}}]},"pokemon-cooldown-palette-v1":{"setup":[{"id":"ram-tile","op":"teleport","args":{"map":33,"x":585,"z":407,"facing":1}},{"id":"spawn-onix","op":"spawn","args":{"species":95,"form":0,"role":"wild","level":5,"x":585,"z":402}},{"id":"bind-onix","op":"bind","args":{"subject":"onix"}}],"actions":[{"id":"first-natural-charge","op":"step","args":{"frames":120,"keys":[],"until":{"kind":"measurement-stage","measurement":"pokemon-cooldown-palette-v1","stage":"attack-started","when":"final"}}},{"id":"dodge-first-charge","op":"step","args":{"frames":16,"keys":["RIGHT"]}},{"id":"ordinary-first-crash","op":"step","args":{"frames":480,"keys":[],"until":{"kind":"measurement-stage","measurement":"pokemon-cooldown-palette-v1","stage":"crashed","when":"final"}}},{"id":"blue-and-natural-expiry","op":"wait","args":{"predicate":{"kind":"measurement-complete","measurement":"pokemon-cooldown-palette-v1","when":"final"}}}]}}')

for _phases in RECIPE_ACTIONS.values():
    for _rows in _phases.values():
        for _row in _rows:
            for _name in ("predicate", "until"):
                if _name in _row["args"]: _row["args"][_name].setdefault("when", "final")

def validate_recipe(test, measurement):
    kind=measurement["kind"];config=CONFIG[kind]
    need(test["id"]==config["id"] and test["mode"]=="prepared"
         and measurement==dict(kind=kind,subject=config["subjects"][0][0])
         and test["requirements"]==[config["requirement"]]
         and test["subjects"]==[dict(id=n,species=s,role=r,acquire=a) for n,s,r,a in config["subjects"]]
         and test["budgets"]["minObservedFrames"]==config["minimum"],"recipe subjects/claims differ")
    for phase in ("setup","actions"):
        need([{k:r[k] for k in ("id","op","args")} for r in test[phase]]==RECIPE_ACTIONS[kind][phase],
             "recipe input/setup order differs")
    if kind==DAMAGE:
        need(test["actions"][1]["budget"]==dict(maxSeconds=30,maxFrames=32,noProgressFrames=32),
             "hit-settlement wait budget differs")
    need(test["assertions"]==[dict(kind="measurement-complete",measurement=kind,when="final")],
         "recipe completion gate differs")

RECIPE_ACTIONS[AMBUSH_COOLDOWN] = {'setup': [{'id': 'ambush-tile', 'op': 'teleport', 'args': {'map': 33, 'x': 585, 'z': 403, 'facing': 0}}, {'id': 'spawn-weepinbell', 'op': 'spawn', 'args': {'species': 70, 'form': 0, 'role': 'wild', 'level': 5, 'x': 585, 'z': 402}}, {'id': 'bind-weepinbell', 'op': 'bind', 'args': {'subject': 'weepinbell'}}], 'actions': [{'id': 'first-natural-attack', 'op': 'wait', 'args': {'predicate': {'kind': 'measurement-stage', 'measurement': 'pokemon-ambush-cooldown-palette-v1', 'stage': 'attack-started', 'when': 'final'}}}, {'id': 'first-natural-expiry', 'op': 'wait', 'args': {'predicate': {'kind': 'measurement-stage', 'measurement': 'pokemon-ambush-cooldown-palette-v1', 'stage': 'attack-ended', 'when': 'final'}}}, {'id': 'blue-and-natural-expiry', 'op': 'wait', 'args': {'predicate': {'kind': 'measurement-complete', 'measurement': 'pokemon-ambush-cooldown-palette-v1', 'when': 'final'}}}]}

# Prepared own-cooldown cases keep the saved Mankey from taking the attack
# subject through its intended sight/accepted-hit Throw reaction. These are
# ordinary native party/spawn setup operations, never profile/timer writes.
for _kind in (COOLDOWN, AMBUSH_COOLDOWN):
    RECIPE_ACTIONS[_kind]["setup"][1:1] = [
        {"id": "prepare-passive-follower", "op": "party",
         "args": {"slot": 0, "species": 155, "level": 20}},
        {"id": "create-passive-follower", "op": "spawn",
         "args": {"species": 155, "form": 0, "role": "follower", "slot": 0, "level": 20}}]
