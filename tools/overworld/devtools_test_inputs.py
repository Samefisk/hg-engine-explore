"""Fixed source inputs for shared measurement, used by execution and replay.

Recipes cannot select a Python module or a source path. No engine or acceptance
is owned here; the enclosing job/controller seals the current source identity.
"""
import hashlib
import json

def cargo_query_image():
    from tools.overworld.devtools_query_observer import ELF_SHA, PACKAGE_SHA
    return dict(elfSha256=ELF_SHA, packageSha256=PACKAGE_SHA)



def measurement_inputs(test, root):
    if not test.get("measurements"):
        return {}
    if test["measurements"] == [{"kind": "route30-sentret-throw-pacing-v1", "subject": "mankey"}]:
        template = {**test, "measurements": [{"kind": "follower-throw-moving-cargo-v1", "subject": "mankey"}]}
        source = measurement_inputs(template, root)["follower-throw-moving-cargo-v1"]
        source["sourceSaveSha256"] = hashlib.sha256((root / test["fixture"]["save"]).read_bytes()).hexdigest()
        return {"route30-sentret-throw-pacing-v1": source}
    if test["measurements"] == [{"kind": "population-headroom-v1", "subject": "mankey"}]:
        # Product spawn, population and profile sources reach the ROM; name the
        # authored profile bytes as well so a profile edit cannot reuse the run.
        digest = hashlib.sha256()
        with (root / test["fixture"]["rom"]).open("rb") as rom:
            for chunk in iter(lambda: rom.read(1024 * 1024), b""):
                digest.update(chunk)
        return {"population-headroom-v1": {
            "contractVersion": 1, "romSha256": digest.hexdigest(),
            "sourceSaveSha256": hashlib.sha256((root / test["fixture"]["save"]).read_bytes()).hexdigest(),
            "profileSha256": hashlib.sha256(
                (root / "data/overworld_behavior_profiles.json").read_bytes()).hexdigest()}}
    if len(test["measurements"]) == 1 and test["measurements"][0]["kind"] in (
            "pokemon-damage-palette-v1", "pokemon-cooldown-palette-v1", "pokemon-ambush-cooldown-palette-v1"):
        descriptor = json.loads((root / "build/player-health.debug.json").read_text())
        if descriptor.get("formatVersion") != 1 or descriptor.get("overlay", {}).get("id") != 161:
            raise ValueError("Pokémon palette HP owner descriptor differs")
        paths = {"romSha256": test["fixture"]["rom"],
                 "capsuleElfSha256": "build/overworld_field_capsule_linked.o",
                 "behaviorBlobSha256": "build/OverworldWildBehaviorData.bin",
                 "profileSha256": "data/overworld_behavior_profiles.json"}
        source = {key: hashlib.sha256((root / path).read_bytes()).hexdigest() for key,path in paths.items()}
        source.update(contractVersion=1, overlaySha256=descriptor["overlay"]["sha256"])
        return {test["measurements"][0]["kind"]: source}
    if len(test["measurements"]) == 1 and test["measurements"][0]["kind"] in (
            "distance-despawn-route29-v1", "distance-despawn-cherrygrove-v1"):
        from tools.overworld.devtools_field_cleanup import symbol
        descriptor = json.loads((root / "build/player-health.debug.json").read_text())
        if descriptor.get("formatVersion") != 1 or descriptor.get("overlay",{}).get("id") != 161:
            raise ValueError("distance claim HP owner descriptor differs")
        native = symbol((root / "build/overworld_wild_helper_overlay_linked.o").read_bytes(),
                        "OverworldWildHelper_DespawnFarEncounters",2,expected_size=332)
        source = dict(contractVersion=1,romSha256=hashlib.sha256((root/test["fixture"]["rom"]).read_bytes()).hexdigest(),
                      overlaySha256=descriptor["overlay"]["sha256"],helperAddress=native[0],
                      helperEntrySha256=hashlib.sha256(native[2][:32]).hexdigest())
        return {test["measurements"][0]["kind"]:source}
    if test["measurements"] == [{"kind": "player-health-zero-load-v1"}]:
        descriptor = json.loads((root / "build/player-health.debug.json").read_text())
        if descriptor.get("formatVersion") != 1 or descriptor.get("overlay", {}).get("id") != 161:
            raise ValueError("player HP descriptor version or overlay differs")
        rom = hashlib.sha256((root / test["fixture"]["rom"]).read_bytes()).hexdigest()
        source_save = hashlib.sha256((root / test["fixture"]["save"]).read_bytes()).hexdigest()
        return {"player-health-zero-load-v1": {
            "contractVersion": 1, "overlaySha256": descriptor["overlay"]["sha256"],
            "romSha256": rom, "sourceSaveSha256": source_save}}
    if test["measurements"] in ([{"kind": "player-health-initial-state-v1"}],
                                 [{"kind": "player-health-ram-rest-v1", "subject": "onix"}],
                                 [{"kind": "player-health-ram-low-speed-v1", "subject": "onix"}],
                                 [{"kind": "player-health-bar-v1", "subject": "onix"}],
                                 [{"kind": "player-health-ram-warning-v1", "subject": "onix"}],
                                 [{"kind": "player-health-save-reload-v1", "subject": "onix"}],
                                 [{"kind": "player-health-throw-contact-v1",
                                   "subjects": ["weepinbell", "geodude"]}],
                                 [{"kind": "player-health-hop-contact-v1", "subject": "mankey"}],
                                 [{"kind": "player-health-ambush-jump-v1", "subject": "weepinbell"}],
                                 [{"kind": "player-health-running-hit-v1", "subject": "weepinbell"}],
                                 [{"kind": "player-health-mounted-ambush-height-v1", "subjects": ["cyndaquil", "weepinbell"]}],
                                 [{"kind": "follower-throw-moving-cargo-v1", "subject": "mankey"}],
                                 [{"kind": "follower-throw-away-non45-v1", "subject": "mankey"}],
                                 [{"kind": "follower-throw-approach-cargo-v1", "subject": "mankey"}],
                                 [{"kind": "follower-throw-player-damage-v1", "subject": "mankey"}],
                                 [{"kind": "follower-throw-query-priority-v1", "subject": "mankey"}],
                                 [{"kind": "wild-throw-ground-lock-soak-v1", "subject": "geodude-a"}],
                                 [{"kind": "throw-cargo-competition-v1", "subject": "far-geodude"}],
                                 [{"kind": "throw-cargo-retarget-v1", "subject": "geodude"}],
                                 [{"kind": "throw-mutual-pickup-v1", "subject": "geodude-a"}],
                                 [{"kind": "follower-throw-target-above-v1", "subject": "mankey"}],
                                 [{"kind": "follower-throw-target-below-v1", "subject": "mankey"}],
                                 [{"kind": "follower-target-access-signpost-v1", "subject": "mankey"}],
                                 [{"kind": "follower-target-access-ground-v1", "subject": "mankey"}],
                                 [{"kind": "throw-cargo-flee-v1", "subject": "cargo"}],
                                 [{"kind": "baby-wild-player-fear-v1", "subject": "baby"}],
                                 [{"kind": "baby-wild-igglybuff-cry-v1", "subject": "baby"}],
                                 [{"kind": "baby-wild-pokemon-fear-v1", "subject": "baby"}],
                                 [{"kind": "baby-follower-safety-v1", "subject": "baby"}],
                                 [{"kind": "baby-follower-damaged-v1", "subject": "baby"}],
                                 [{"kind": "wild-damaged-flee-v1", "subject": "cleffa"}],
                                 [{"kind": "playful-in-place-hop-v1", "subject": "clefairy"}],
                                 [{"kind": "stomp-slam-player-contact-v1", "subject": "snorlax"}],
                                 [{"kind": "stomp-slam-mounted-player-contact-v1", "subject": "snorlax"}],
                                 [{"kind": "mounted-rattata-walking-ledge-v1", "subject": "rattata"}],
                                 [{"kind": "held-throw-search-v1", "subject": "geodude"}],
                                 [{"kind": "player-health-moving-heal-on-foot-v1", "subject": "weepinbell"}],
                                 [{"kind": "player-health-moving-heal-mounted-v1", "subject": "weepinbell"}],
                                 [{"kind": "pokemon-combat-v1", "subject": "cyndaquil"}],
                                 [{"kind": "pokemon-skid-hit-v1", "subject": "stantler"}],
                                 [{"kind": "follower-ram-pokemon-v1", "subject": "onix"}],
                                 [{"kind": "basic-attack-v1", "subject": "snorlax"}],
                                 [{"kind": "player-health-mounted-throw-v1",
                                   "subjects": ["cyndaquil", "bellsprout", "geodude"]}]):
        descriptor = json.loads((root / "build/player-health.debug.json").read_text())
        if descriptor.get("formatVersion") != 1 or descriptor.get("overlay", {}).get("id") != 161:
            raise ValueError("player HP descriptor version or overlay differs")
        if test["id"] == "player-hp.initial-state" \
                and b"PH\x01" in (root / test["fixture"]["save"]).read_bytes():
            raise ValueError("player HP initial-state fixture already contains an HP record")
        digest = hashlib.sha256()
        with (root / test["fixture"]["rom"]).open("rb") as rom:
            for chunk in iter(lambda: rom.read(1024 * 1024), b""):
                digest.update(chunk)
        source = {
            "contractVersion": 1,
            "overlaySha256": descriptor["overlay"]["sha256"],
            "romSha256": digest.hexdigest(),
        }
        if test["measurements"][0]["kind"] in ("player-health-hop-contact-v1", "player-health-ambush-jump-v1", "player-health-running-hit-v1",
                                                 "player-health-mounted-ambush-height-v1", "pokemon-combat-v1", "pokemon-skid-hit-v1", "follower-ram-pokemon-v1", "basic-attack-v1",
                                                 "player-health-moving-heal-on-foot-v1", "player-health-moving-heal-mounted-v1", "throw-cargo-flee-v1", "held-throw-search-v1", "baby-wild-player-fear-v1", "baby-wild-igglybuff-cry-v1", "baby-wild-pokemon-fear-v1", "baby-follower-safety-v1", "baby-follower-damaged-v1", "wild-damaged-flee-v1", "playful-in-place-hop-v1", "stomp-slam-player-contact-v1", "stomp-slam-mounted-player-contact-v1", "mounted-rattata-walking-ledge-v1",
                                                 "follower-throw-target-above-v1", "follower-throw-target-below-v1", "follower-throw-moving-cargo-v1", "follower-throw-away-non45-v1", "follower-throw-approach-cargo-v1", "follower-throw-player-damage-v1", "follower-throw-query-priority-v1", "wild-throw-ground-lock-soak-v1", "throw-cargo-competition-v1", "throw-cargo-retarget-v1", "throw-mutual-pickup-v1", "follower-target-access-signpost-v1", "follower-target-access-ground-v1"):
            source["profileSha256"] = hashlib.sha256(
                (root / "data/overworld_behavior_profiles.json").read_bytes()).hexdigest()
        if test["measurements"][0]["kind"] in ("follower-throw-moving-cargo-v1", "follower-throw-away-non45-v1", "follower-throw-approach-cargo-v1", "follower-throw-player-damage-v1", "follower-throw-query-priority-v1", "wild-throw-ground-lock-soak-v1", "throw-cargo-competition-v1", "throw-cargo-retarget-v1", "throw-mutual-pickup-v1"):
            source.update(contractVersion=2, queryImage=cargo_query_image())
        if test["measurements"][0]["kind"] == "wild-throw-ground-lock-soak-v1":
            from tools.overworld.devtools_field_cleanup import symbol
            native = symbol((root / "build/overworld_wild_helper_overlay_linked.o").read_bytes(),
                            "OverworldWildHelper_DespawnFarEncounters",2,expected_size=332)
            source.update(helperAddress=native[0], helperEntrySha256=hashlib.sha256(native[2][:32]).hexdigest())
        return {test["measurements"][0]["kind"]: source}
    if test["measurements"] == [{"kind": "wild-throw-moving-candidate-v1",
                                 "subjects": ["stantler", "geodude"]}]:
        descriptor = json.loads((root / "build/player-health.debug.json").read_text())
        if descriptor.get("formatVersion") != 1 or descriptor.get("overlay", {}).get("id") != 161:
            raise ValueError("moving Wild Throw HP owner descriptor differs")
        digest = hashlib.sha256()
        with (root / test["fixture"]["rom"]).open("rb") as rom:
            for chunk in iter(lambda: rom.read(1024 * 1024), b""):
                digest.update(chunk)
        return {"wild-throw-moving-candidate-v1": {
            "contractVersion": 2, "romSha256": digest.hexdigest(),
            "overlaySha256": descriptor["overlay"]["sha256"],
            "profileSha256": hashlib.sha256((root/"data/overworld_behavior_profiles.json").read_bytes()).hexdigest(),
            "queryImage": cargo_query_image()}}
    fixed_contract = ("unmounted-cadence-v1", "unmounted-game-cadence-v1", "center-entry-exit-v1", "cyndaquil-normal-setup-v1", "live-route-control-v1", "packaged-resolver-parity-v1", "packaged-condition-service-v1", "actor-binding-context-v1", "actor-inspect-handle-v1", "live-walk-policy-control-v1", "mounted-frame-pacing-v1", "mounted-control-stress-v1", "mount-detach-follower-resume-v1", "live-mount-pose-control-v1", "wild-walk-v1", "wild-ledge-v1", "wild-teleport-v1", "runner-stop-skid-v1", "runner-turn-runway-v1", "appear-hop-timing-v1", "wild-transition-invalidation-v1", "follower-transition-rebind-v1", "mounted-streaming-path-v1", "mounted-cardinal-streaming-v1", "mounted-walk-transition-v1", "land-surf-separation-v1", "population-fast-travel-v1", "mounted-teleport-matrix-v1", "live-wild-clear-control-v1", "turn-skid-v1", "wild-battle-handoff-v1", "warp-gate-v1", "diagonal-corner-v1", "live-corner-control-v1", "mounted-frame-matrix-v1", "live-walk-matrix-control-v1", "mounted-stomp-v1", "live-stomp-control-v1", "mounted-crash-v1", "live-crash-control-v1", "live-condition-controller-v1", "stalker-runtime-v1", "playful-runtime-v1", "startled-runtime-v1", "fly-in-runtime-v1", "waddle-runtime-v1", "held-control-runtime-v1")
    fixed_contract += ("blocked-wild-facing-v1", "mounted-speed-slew-v1",
                       "floaty-bounce-hop-pause-v1", "ambush-player-landing-v1",
                       "follower-stop-facing-v1", "ram-until-crash-v1", "ram-behind-entry-v1", "ram-ledge-continuity-v1", "ram-brief-notice-v1", "throw-notice-walk-commit-v1", "follower-throw-hit-abort-v1")
    fixed_contract += ("emote-three-slots-v1", "natural-refill-retry-v1", "natural-water-spawn-v1")
    fixed_contract += ("wild-roof-rebind-height-v1", "wild-signpost-rebind-height-v1")
    if all(item["kind"] in fixed_contract for item in test["measurements"]):
        # Setup transitions are already in the immutable typed recipe. Do not
        # add unrelated profile reads to a fixed-contract route measurement.
        return {item["kind"]: {"contractVersion": 1} for item in test["measurements"]}
    raw_profiles = (root / "data/overworld_behavior_profiles.json").read_bytes()
    source = {
        "schema": json.loads((root / "tools/overworld/behavior_schema.json").read_text()),
        "sourceSha256": hashlib.sha256(raw_profiles).hexdigest(),
    }
    if any(item["kind"] == "unmounted-zero-stutter-v1"
           for item in test["measurements"]):
        return {item["kind"]: (source
                if item["kind"] == "unmounted-zero-stutter-v1"
                else {"contractVersion": 1})
                for item in test["measurements"]}
    # Retain authored POOL meaning from the same bytes as its sealed digest.
    # Existing measurements keep their exact, two-key input contract.
    return {item["kind"]: ({**source, "authoredProfiles": json.loads(raw_profiles)}
                          if item["kind"] in ("pool-spawn-v1", "pool-spawn-surface-v1", "live-spawn-height-control-v1") else source)
            for item in test["measurements"]}
