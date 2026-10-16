"""Check the authenticated before/after boundary of Mom's completed Rest.

This is a draft boundary checker. A registered raw-record adapter must also
authenticate the normal menu input before this can count as accepted proof.
"""

KIND = "player-health-home-rest-v1"
REQUIREMENT = "current.player-health-home-rest"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _boundary(row, source):
    require(isinstance(row, dict) and row.get("command") == "player-health.observe",
            "home Rest needs a checked HP read")
    snapshot = row.get("snapshot")
    receipt = row.get("receipt", {}).get("playerHealth")
    require(isinstance(snapshot, dict) and isinstance(receipt, dict),
            "home Rest snapshot or HP receipt is missing")
    identity = receipt.get("identity", {})
    require(receipt.get("schemaVersion") == 1
            and identity.get("descriptorVersion") == 1
            and identity.get("overlayId") == 161
            and identity.get("overlaySha256") == source["overlaySha256"]
            and identity.get("romSha256") == source["romSha256"]
            and snapshot.get("romSha256") == source["romSha256"]
            and receipt.get("frame") == snapshot.get("frame")
            and receipt.get("nativeCycle") == snapshot.get("nativeCycle"),
            "home Rest read has wrong package or clock identity")
    require(snapshot.get("fieldAvailable") is True
            and snapshot.get("observationBoundary") == "main-task-queue-completion"
            and snapshot.get("context", {}).get("mapId") == 63
            and snapshot.get("fieldControl", {}).get("taskPointer") == 0
            and snapshot.get("dialogue", {}).get("state") == "idle"
            and snapshot.get("dialogue", {}).get("known") is True
            and (snapshot.get("player", {}).get("x"),
                 snapshot.get("player", {}).get("y")) == (6, 8)
            and receipt.get("observationBoundary") == "main-task-queue-completion"
            and receipt.get("context") == snapshot.get("context")
            and receipt.get("maxHp") == 100
            and receipt.get("hp") == receipt.get("savedHp")
            and receipt.get("recoveryPending") is False,
            "home Rest read is not the idle Mom field boundary")
    party = snapshot.get("party")
    observation = snapshot.get("partyObservation", {})
    require(isinstance(party, list) and party and isinstance(party[0], dict)
            and observation.get("frame") == snapshot["frame"]
            and observation.get("boundary") == "main-task-queue-completion",
            "home Rest party getter is missing or stale")
    return snapshot, receipt, party[0]


def check_home_rest(before_row, after_row, source):
    """Return the exact trainer, party and checkpoint result or reject it."""
    before_snap, before_hp, before_mon = _boundary(before_row, source)
    after_snap, after_hp, after_mon = _boundary(after_row, source)
    require(after_snap["frame"] > before_snap["frame"]
            and after_snap["nativeCycle"] > before_snap["nativeCycle"],
            "home Rest did not advance the game clock")
    require(before_hp.get("hp") == 67
            and before_hp.get("lastDamage") == 33
            and type(before_hp.get("acceptedHits")) is int
            and before_hp["acceptedHits"] >= 1
            and type(before_hp.get("checkpointSpawn")) is int
            and 2 <= before_hp["checkpointSpawn"] <= 30,
            "home Rest did not start injured at a non-Mom checkpoint")
    require(after_hp.get("hp") == 100
            and after_hp.get("checkpointSpawn") == 1,
            "home Rest did not restore trainer HP and Mom checkpoint")
    identity = ("species", "form", "level", "personality", "maxHp")
    require(all(before_mon.get(key) == after_mon.get(key) for key in identity)
            and type(before_mon.get("maxHp")) is int
            and before_mon["maxHp"] > 1
            and before_mon.get("hp") == 1
            and after_mon.get("hp") == after_mon["maxHp"]
            and after_mon.get("status") == 0,
            "home Rest did not heal the same party Pokémon")
    return {"passed": True, "playerHp": [67, 100],
            "partyHp": [1, after_mon["maxHp"]],
            "checkpointSpawn": [before_hp["checkpointSpawn"], 1],
            "completedGameFrames": after_snap["frame"] - before_snap["frame"]}
