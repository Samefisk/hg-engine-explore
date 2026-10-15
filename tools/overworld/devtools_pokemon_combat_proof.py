"""Controller acceptance and copied-data controls for Pokémon collision HP."""

from copy import deepcopy
import struct

from tools.overworld.devtools_pokemon_combat_measurement import KIND, REQUIREMENT, MIN_FRAMES
from tools.overworld.devtools_walk_matrix_observer import decode_motion


NAMES = {
    "live-actor-identity": ("current-wild-victim-mount-and-attacker",),
    "profile-resolution": ("one-active-ambush-contact-profile",),
    "engine-boundary": ("real-wild-and-party-hp-loss", "same-collision-damages-rider-and-mount", "per-target-hit-guard-and-no-self-hit"),
    "rendered-motion": ("wild-and-mounted-jump-knockbacks-land",),
    "natural-input": ("unforced-ambush-hop",),
    "control-release": ("wild-control-and-mounted-seat-restored",),
}
CLAIMS = tuple(NAMES)
FAULTS = ("combat-missing-hp", "combat-stale-target", "combat-wrong-wild-hp",
          "combat-party-hp-shadow", "combat-no-jump", "combat-seat-height",
          "combat-self-hit", "combat-attack-off", "combat-missing-plan",
          "combat-ordinary-hop", "combat-wrong-jump-duration", "combat-missing-start",
          "combat-missing-control-release", "combat-pending-not-acknowledged", "combat-no-hp-hit")


def contract():
    return {claim: [dict(name=name, operator="eq", type="integer",
                        validator="meaningful-observation", expected=1)
                    for name in names] for claim, names in NAMES.items()}


def measurements(replay, record):
    meter = replay.get("measurements", {}).get(KIND, {})
    jumps = meter.get("forcedKnockbacks", {})
    if (replay.get("passed") is not True or replay.get("failures") != []
            or meter.get("ready") is not True or meter.get("passed") is not True
            or meter.get("acceptedProof") is not False
            or meter.get("observedFrames", 0) < MIN_FRAMES
            or meter.get("observedFrames") != replay.get("observedFrames")
            or meter.get("attackFrames", 0) < 1
            or meter.get("protectedFrames", 0) < 10
            or not all(meter.get("hits", {}).values())
            or not all(meter.get("jumpArcs", {}).values())
            or not all(meter.get("landed", {}).values())
            or set(jumps) != {"snorlax", "cyndaquil"}
            or any(jump.get("finished") is not True or jump.get("queuedAcknowledged") is not True
                   or any(jump.get("plan", {}).get(key) != value for key, value in
                          (("kind", 2), ("duration", 13), ("distance", 1), ("arcHeightQ4", 16),
                           ("flags", 1), ("commitPolicy", 1))) for jump in jumps.values())
            or set(meter.get("subjects", {})) != {"cyndaquil", "snorlax", "weepinbell"}):
        raise ValueError("Pokémon combat lacks real HP loss and completed shared knockback proof")
    if record.get("sessionCleanup") != dict(sessionId=record.get("sessionId"), closed=True, errors=[]):
        raise ValueError("Pokémon combat private session did not close")
    return [dict(claim=claim, name=name, value=1, operator="eq", expected=1, passed=True)
            for claim, names in NAMES.items() for name in names]


class PokemonCombatNegative:
    def __init__(self, fault):
        if fault not in FAULTS:
            raise ValueError("unknown Pokémon combat copied-data control")
        self.fault = fault
        self.applied = False

    def mutate(self, row, subjects):
        changed = deepcopy(row)
        if row.get("phase") != "observe":
            return row
        samples = list(changed.get("samples", []))
        if isinstance(changed.get("snapshot"), dict):
            samples.append(changed["snapshot"])
        for sample in samples:
            combat = sample.get("pokemonCombat", {})
            targets = combat.get("targets", [])
            wild = next((target for target in targets if target.get("species") == 143), None)
            mount = next((target for target in targets if target.get("species") == 155), None)
            source = next((target for target in targets if target.get("species") == 70), None)
            if self.fault == "combat-missing-hp":
                sample.pop("pokemonCombat", None)
                self.applied = True
            elif self.fault == "combat-stale-target" and wild:
                wild["handle"]["encounterGeneration"] += 1
                self.applied = True
            elif self.fault == "combat-wrong-wild-hp" and wild and wild.get("hitCount", 0):
                wild["hp"] = wild["currentHp"] = wild["maxHp"]
                self.applied = True
            elif self.fault == "combat-party-hp-shadow" and mount and mount.get("hitCount", 0):
                for mon in sample.get("party", []):
                    if mon.get("personality") == mount.get("personality"):
                        mon["hp"] = mon["maxHp"]
                        self.applied = True
            elif self.fault == "combat-no-jump" and wild and wild.get("hitCount", 0):
                for actor in sample.get("actors", []):
                    if actor.get("species") == 143:
                        actor["engineObject"]["pos_y"] = 0
                        actor["engineObject"]["face_y"] = 0
                        actor["engineObject"]["unk88_y"] = 0
                        self.applied = True
            elif self.fault == "combat-seat-height" and mount and mount.get("hitCount", 0):
                sample["player"]["face_y"] += 4096
                self.applied = True
            elif self.fault == "combat-self-hit" and source:
                source["hitCount"] += 1
                self.applied = True
            elif self.fault == "combat-missing-plan" and wild and wild.get("hitCount", 0):
                wild.pop("motion", None)
                self.applied = True
            elif self.fault == "combat-no-hp-hit" and wild and wild.get("hitCount", 0):
                wild.update(hp=wild["maxHp"],currentHp=wild["maxHp"],hitCount=0,lastDamage=0,immunityFrames=0)
                self.applied = True
            if wild and wild.get("motion", {}).get("plan", {}).get("flags") == 1:
                if self.fault in ("combat-ordinary-hop", "combat-wrong-jump-duration"):
                    raw = bytearray.fromhex(wild["motion"]["rawHex"])
                    if self.fault == "combat-ordinary-hop":
                        raw[37] = 0
                    else:
                        struct.pack_into("<H", raw, 24, 14)
                    wild["motion"] = decode_motion(bytes(raw))
                    self.applied = True
                elif self.fault == "combat-pending-not-acknowledged":
                    wild["knockbackPending"] = 1
                    self.applied = True
        if self.fault in ("combat-missing-start", "combat-missing-control-release"):
            name = "MOTION_STARTED" if self.fault == "combat-missing-start" else "CONTROL_RETURNED"
            handle = subjects.get("snorlax", {}).get("handle", {}).get("value")
            events = changed.get("events", [])
            kept = [event for event in events if not (event.get("kind") == "native"
                    and event.get("data", {}).get("actorHandle") == handle
                    and event["data"].get("event") == name)]
            if len(kept) != len(events):
                changed["events"] = kept
                self.applied = True
        if self.fault == "combat-attack-off":
            for profile in changed.get("profileCache", {}).get("resolvedProfiles", []):
                if profile.get("appliedOverrides", 0) & (1 << 25):
                    data = bytearray.fromhex(profile["resultHex"])
                    data[72] = 0
                    profile["resultHex"] = data.hex()
                    self.applied = True
        return changed


def validate_negative_result(result, fault):
    if fault not in FAULTS or result.get("passed") is not False or not result.get("failures"):
        raise ValueError("Pokémon combat control did not reject " + fault)
    return True
