"""Explicit lazy dispatch for matching native proof adapters.

This table owns routing only. Feature modules still own exact contracts,
measurements and copied-fault meanings. The controller still owns retained
record replay, session cleanup, same-reader requirements and acceptance.
No plugin discovery, new recorder, or alternative replay path is provided.
"""
from dataclasses import dataclass
from importlib import import_module
from types import MappingProxyType


@dataclass(frozen=True)
class ProofAdapter:
    kind: str
    module_name: str
    negative_name: str
    recorder_control_requirement: str | None
    proof_level: str = 'S3'
    mode: str = 'prepared'
    subjects: tuple = (('cyndaquil', 155, 'MOUNTED', 'existing'),)
    feature: str | None = None

    @property
    def module(self):
        module=import_module('tools.overworld.'+self.module_name)
        if self.feature is None and module.KIND!=self.kind:
            raise ValueError('proof adapter kind differs: '+self.kind)
        return module

    @property
    def requirement(self):
        return self.module.REQUIREMENT if self.feature is None \
            else self.module.requirement(self.feature)

    @property
    def claims(self):
        return tuple(self.module.CLAIMS) if self.feature is None \
            else tuple(self.module.claims(self.feature))

    @property
    def faults(self):
        return tuple(self.module.FAULTS) if self.feature is None \
            else tuple(self.module.faults(self.feature))

    @property
    def is_control(self):return self.mode == 'observer-control'

    def contract(self):
        return self.module.contract() if self.feature is None \
            else self.module.contract(self.feature)

    def measurements(self,replay,record):
        return self.module.measurements(replay,record) if self.feature is None \
            else self.module.measurements(self.feature,replay,record)

    def negative(self,fault):
        # Keep the existing constructor's fault validation and exception text.
        cls=getattr(self.module,self.negative_name)
        return cls(fault) if self.feature is None else cls(self.feature,fault)

    def validate_negative_result(self,result,fault):
        return self.module.validate_negative_result(result,fault) \
            if self.feature is None else \
            self.module.validate_negative_result(self.feature,result,fault)

    def recipe_subjects(self):
        return [dict(id=name,species=species,role=role,acquire=acquire)
                for name,species,role,acquire in self.subjects]


ADAPTERS=MappingProxyType({adapter.kind:adapter for adapter in (
    ProofAdapter('route30-sentret-throw-pacing-v1', 'devtools_sentret_throw_proof',
        'SentretThrowNegative', None, subjects=(('mankey',56,'FOLLOWER','existing'),
            ('sentret-a',161,'WILD','spawn'),('sentret-b',161,'WILD','spawn'),
            ('sentret-c',161,'WILD','spawn'),('cargo',69,'WILD','spawn'))),
    ProofAdapter('population-headroom-v1', 'devtools_population_headroom_proof',
        'PopulationHeadroomNegative', None, subjects=(('mankey',56,'FOLLOWER','existing'),)),
    ProofAdapter('natural-refill-retry-v1', 'devtools_spawn_priority_proof',
        'SpawnPriorityNegative', None, subjects=(('mankey',56,'FOLLOWER','existing'),), feature='natural-refill-retry-v1'),
    ProofAdapter('natural-water-spawn-v1', 'devtools_spawn_priority_proof',
        'SpawnPriorityNegative', None, subjects=(('mankey',56,'FOLLOWER','existing'),), feature='natural-water-spawn-v1'),
    ProofAdapter('emote-three-slots-v1' , 'devtools_emote_three_proof',
        'EmoteThreeNegative', None, subjects=tuple((n,155,'WILD','spawn') for n in 'abcd')),
    ProofAdapter('follower-target-access-signpost-v1', 'devtools_target_access_proof',
        'TargetAccessNegative', None, subjects=(('mankey',56,'FOLLOWER','existing'),('target',16,'WILD','spawn')),
        feature='follower-target-access-signpost-v1'),
    ProofAdapter('follower-target-access-ground-v1', 'devtools_target_access_proof',
        'TargetAccessNegative', None, subjects=(('mankey',56,'FOLLOWER','existing'),('target',143,'WILD','spawn')),
        feature='follower-target-access-ground-v1'),
    ProofAdapter('throw-cargo-competition-v1', 'devtools_throw_cargo_competition_proof',
        'ThrowCargoCompetitionNegative', None, subjects=(('far-geodude',74,'WILD','spawn'),
            ('cargo',155,'WILD','spawn'),('near-geodude',74,'WILD','spawn'))),
    ProofAdapter('throw-cargo-retarget-v1', 'devtools_throw_cargo_retarget_proof',
        'ThrowCargoRetargetNegative', None, subjects=(('geodude',74,'WILD','spawn'),
            ('first-cargo',155,'WILD','spawn'),('near-cargo',70,'WILD','spawn'))),
    ProofAdapter('throw-mutual-pickup-v1', 'devtools_throw_mutual_pickup_proof',
        'ThrowMutualPickupNegative', None, subjects=(('geodude-a',74,'WILD','spawn'),
            ('geodude-b',74,'WILD','spawn'))),
    ProofAdapter('wild-throw-ground-lock-soak-v1', 'devtools_wild_throw_soak_proof',
        'WildThrowSoakNegative', None, 'S5', subjects=(('geodude-a',74,'WILD','spawn'),
            ('geodude-b',74,'WILD','spawn'),('geodude-c',74,'WILD','spawn'),
            ('cargo',70,'WILD','spawn'),('passive',155,'FOLLOWER','existing'))),
    ProofAdapter('basic-attack-v1', 'devtools_basic_attack_measurement',
        'BasicAttackNegative', None, 'S4', subjects=(('snorlax',143,'WILD','spawn'),
            ('cyndaquil',155,'WILD','spawn'),('passive',174,'FOLLOWER','existing'))),
    ProofAdapter('follower-ram-pokemon-v1', 'devtools_follower_ram_proof',
        'FollowerRamNegative', None, 'S4', subjects=(('onix',95,'FOLLOWER','existing'),
            ('snorlax',143,'WILD','spawn'))),
    ProofAdapter("player-health-running-hit-v1", "devtools_player_health_running_hit_proof",
        "RunningHitNegative", None, subjects=(("weepinbell",70,"WILD","spawn"),)),
    ProofAdapter('distance-despawn-route29-v1', 'devtools_distance_despawn_proof',
        'DistanceDespawnNegative', None, subjects=(('cargo',179,'WILD','spawn'),('carrier',74,'WILD','spawn'),('unrelated',143,'WILD','spawn')),
        feature='distance-despawn-route29-v1'),
    ProofAdapter('distance-despawn-cherrygrove-v1', 'devtools_distance_despawn_proof',
        'DistanceDespawnNegative', None, subjects=(('cargo',179,'WILD','spawn'),('carrier',74,'WILD','spawn'),('unrelated',143,'WILD','spawn')),
        feature='distance-despawn-cherrygrove-v1'),
    ProofAdapter('pokemon-damage-palette-v1', 'devtools_appearance_proof',
        'AppearanceNegative', None, 'S4', subjects=(('cyndaquil',155,'MOUNTED','existing'),
            ('snorlax',143,'WILD','spawn'),('weepinbell',70,'WILD','spawn'),
            ('healed-cyndaquil',155,'FOLLOWER','existing')), feature='pokemon-damage-palette-v1'),
    ProofAdapter('pokemon-ambush-cooldown-palette-v1', 'devtools_appearance_proof',
        'AppearanceNegative', None, 'S4', subjects=(('weepinbell',70,'WILD','spawn'),),
        feature='pokemon-ambush-cooldown-palette-v1'),
    ProofAdapter('pokemon-cooldown-palette-v1', 'devtools_appearance_proof',
        'AppearanceNegative', None, 'S4', subjects=(('onix',95,'WILD','spawn'),),
        feature='pokemon-cooldown-palette-v1'),
    ProofAdapter('player-health-moving-heal-on-foot-v1', 'devtools_player_health_moving_heal_proof',
        'MovingHealNegative', None, subjects=(('weepinbell',70,'WILD','spawn'),),
        feature='player-health-moving-heal-on-foot-v1'),
    ProofAdapter('player-health-moving-heal-mounted-v1', 'devtools_player_health_moving_heal_proof',
        'MovingHealNegative', None, subjects=(('weepinbell',70,'WILD','spawn'),('cyndaquil',155,'MOUNTED','existing')),
        feature='player-health-moving-heal-mounted-v1'),
    ProofAdapter('held-throw-search-v1', 'devtools_held_throw_search_proof',
        'HeldThrowSearchNegative', None, subjects=(('geodude',74,'WILD','spawn'),('mareep',179,'WILD','spawn'),('stantler',234,'FOLLOWER','existing'))),
    ProofAdapter('throw-cargo-flee-v1', 'devtools_throw_cargo_flee_proof',
        'ThrowCargoFleeNegative', None, subjects=(('cargo',173,'WILD','spawn'),('geodude',74,'WILD','spawn'))),
    ProofAdapter('baby-wild-player-fear-v1', 'devtools_baby_fear_proof',
        'BabyFearNegative', None, subjects=(('baby',173,'WILD','spawn'),('passive',155,'FOLLOWER','existing')),
        feature='baby-wild-player-fear-v1'),
    ProofAdapter('baby-wild-igglybuff-cry-v1', 'devtools_baby_fear_proof',
        'BabyFearNegative', None, subjects=(('baby',174,'WILD','spawn'),('passive',155,'FOLLOWER','existing')),
        feature='baby-wild-igglybuff-cry-v1'),
    ProofAdapter('baby-wild-pokemon-fear-v1', 'devtools_baby_fear_proof',
        'BabyFearNegative', None, subjects=(('baby',173,'WILD','spawn'),('threat',155,'WILD','spawn'),
                                           ('passive',155,'FOLLOWER','existing')),
        feature='baby-wild-pokemon-fear-v1'),
    ProofAdapter('baby-follower-safety-v1', 'devtools_baby_fear_proof',
        'BabyFearNegative', None, subjects=(('baby',173,'FOLLOWER','existing'),('threat',155,'WILD','spawn')),
        feature='baby-follower-safety-v1'),
    ProofAdapter('baby-follower-damaged-v1', 'devtools_baby_fear_proof',
        'BabyFearNegative', None, subjects=(('baby',173,'FOLLOWER','existing'),('threat',70,'WILD','spawn')),
        feature='baby-follower-damaged-v1'),
    ProofAdapter('wild-damaged-flee-v1', 'devtools_baby_fear_proof',
        'BabyFearNegative', None, subjects=(('cleffa',173,'WILD','spawn'),('threat',70,'WILD','spawn'),
                                           ('passive',155,'FOLLOWER','existing')),
        feature='wild-damaged-flee-v1'),
    ProofAdapter('stomp-slam-mounted-player-contact-v1', 'devtools_stomp_slam_mounted_proof',
        'StompSlamMountedNegative', None, subjects=(('snorlax',143,'WILD','spawn'),
            ('passive',155,'MOUNTED','existing'))),
    ProofAdapter('mounted-rattata-walking-ledge-v1', 'devtools_mounted_rattata_ledge_proof',
        'MountedRattataLedgeNegative', None, subjects=(('rattata',19,'MOUNTED','existing'),)),
    ProofAdapter('stomp-slam-player-contact-v1', 'devtools_stomp_slam_proof',
        'StompSlamNegative', None, subjects=(('snorlax',143,'WILD','spawn'),
            ('passive',155,'FOLLOWER','existing'))),
    ProofAdapter('playful-in-place-hop-v1', 'devtools_playful_hop_proof',
        'PlayfulHopNegative', None, subjects=(('clefairy',35,'WILD','spawn'),
            ('passive',155,'FOLLOWER','existing'))),
    ProofAdapter('follower-throw-target-above-v1', 'devtools_cross_height_throw_proof',
        'CrossHeightThrowNegative', None, subjects=(('mankey', 56, 'FOLLOWER', 'existing'), ('trigger', 70, 'WILD', 'spawn'), ('cargo', 179, 'WILD', 'spawn')), feature='follower-throw-target-above-v1'),
    ProofAdapter('follower-throw-target-below-v1', 'devtools_cross_height_throw_proof',
        'CrossHeightThrowNegative', None, subjects=(('mankey', 56, 'FOLLOWER', 'existing'), ('trigger', 70, 'WILD', 'spawn'), ('cargo', 179, 'WILD', 'spawn')), feature='follower-throw-target-below-v1'),
    ProofAdapter('follower-throw-approach-cargo-v1', 'devtools_follower_throw_approach_proof',
        'FollowerThrowApproachNegative', None, subjects=(("mankey",56,"FOLLOWER","existing"),
            ("trigger",95,"WILD","existing"),("cargo",69,"WILD","spawn"),("alternative",43,"WILD","spawn"))),
    ProofAdapter('follower-throw-query-priority-v1', 'devtools_follower_query_priority_proof',
        'FollowerQueryPriorityNegative', None, subjects=(("mankey",56,"FOLLOWER","existing"),
            ("old-geodude",74,"WILD","spawn"),("source",74,"WILD","spawn"))),
    ProofAdapter('follower-throw-player-damage-v1', 'devtools_damage_follower_proof',
        'DamageFollowerNegative', None, subjects=(('mankey',56,'FOLLOWER','existing'),
            ('source',70,'WILD','spawn'))),
    ProofAdapter('follower-throw-moving-cargo-v1', 'devtools_follower_throw_proof',
        'FollowerThrowNegative', None, subjects=(('mankey',56,'FOLLOWER','existing'),
            ('trigger',69,'WILD','spawn'),('cargo',69,'WILD','spawn'))),
    ProofAdapter('follower-throw-away-non45-v1', 'devtools_follower_throw_proof',
        'FollowerThrowFeatureNegative', None, subjects=(('mankey',56,'FOLLOWER','existing'),
            ('trigger',69,'WILD','spawn'),('cargo',69,'WILD','spawn')), feature='follower-throw-away-non45-v1'),
    ProofAdapter('wild-roof-rebind-height-v1', 'devtools_wild_surface_rebind_proof',
        'WildSurfaceRebindNegative', None, subjects=(('hoothoot',163,'WILD','spawn'),),
        feature='wild-roof-rebind-height-v1'),
    ProofAdapter('wild-signpost-rebind-height-v1', 'devtools_wild_surface_rebind_proof',
        'WildSurfaceRebindNegative', None, subjects=(('pidgey',16,'WILD','spawn'),),
        feature='wild-signpost-rebind-height-v1'),
    ProofAdapter('ram-ledge-continuity-v1', 'devtools_ram_ledge_proof',
        'RamLedgeNegative', None, subjects=(('onix',95,'WILD','spawn'),)),
    ProofAdapter('ram-behind-entry-v1', 'devtools_ram_until_crash_proof',
        'RamFeatureNegative', None, subjects=(('onix',95,'WILD','spawn'),), feature='ram-behind-entry-v1'),
    ProofAdapter('ram-until-crash-v1', 'devtools_ram_until_crash_proof',
        'RamUntilCrashNegative', None, subjects=(('onix',95,'WILD','spawn'),)),
    ProofAdapter('ram-brief-notice-v1', 'devtools_ram_brief_notice_proof',
        'RamBriefNoticeNegative', None, subjects=(('onix',95,'WILD','spawn'),)),
    ProofAdapter('throw-notice-walk-commit-v1', 'devtools_throw_notice_walk_commit_proof',
        'ThrowNoticeWalkCommitNegative', None,
        subjects=(('snorlax',143,'WILD','spawn'),('geodude',74,'WILD','spawn'))),
    ProofAdapter('follower-throw-hit-abort-v1', 'devtools_follower_throw_hit_abort_proof',
        'FollowerThrowHitAbortNegative', None,
        subjects=(('mankey',56,'FOLLOWER','existing'),('onix',95,'WILD','spawn'))),
    ProofAdapter('follower-stop-facing-v1', 'devtools_follower_stop_proof',
        'FollowerStopNegative', None, subjects=(('stantler',234,'FOLLOWER','existing'),)),
    ProofAdapter('pokemon-skid-hit-v1', 'devtools_pokemon_skid_hit_proof',
        'PokemonSkidHitNegative', None, 'S4',
        subjects=(('stantler',234,'MOUNTED','existing'),('weepinbell',70,'WILD','spawn'))),
    ProofAdapter('pokemon-combat-v1', 'devtools_pokemon_combat_proof',
        'PokemonCombatNegative', None, 'S4',
        subjects=(('cyndaquil',155,'MOUNTED','existing'),
                  ('snorlax',143,'WILD','spawn'),('weepinbell',70,'WILD','spawn'))),
    ProofAdapter('diagonal-corner-v1','devtools_corner_proof','CornerNegative',
        'shared.corner-recorder-control-v1'),
    ProofAdapter('live-corner-control-v1','devtools_corner_control_proof','CornerControlNegative',None,mode='observer-control'),
    ProofAdapter('mounted-frame-matrix-v1','devtools_walk_matrix_proof','MatrixNegative',
        'shared.walk-matrix-recorder-control-v1'),
    ProofAdapter('live-walk-matrix-control-v1','devtools_walk_matrix_control_proof','MatrixControlNegative',None,mode='observer-control'),
    ProofAdapter('mounted-stomp-v1','devtools_stomp_proof','StompNegative',
        'shared.stomp-recorder-control-v1'),
    ProofAdapter('live-stomp-control-v1','devtools_stomp_control_proof','StompControlNegative',None,mode='observer-control'),
    ProofAdapter('mounted-crash-v1','devtools_mounted_crash_proof','CrashNegative',
        'shared.crash-recorder-control-v1','S4'),
    ProofAdapter('live-crash-control-v1','devtools_mounted_crash_control_proof','CrashControlNegative',None,mode='observer-control'),
    ProofAdapter('turn-skid-v1','devtools_turn_skid_proof','TurnSkidNegative',
        'shared.walk-matrix-recorder-control-v1', 'S4'),
    ProofAdapter('mount-detach-follower-resume-v1',
        'devtools_mount_detach_follower_resume_proof',
        'MountDetachFollowerResumeNegative',None,'S4'),
    ProofAdapter('mounted-speed-slew-v1', 'devtools_mount_speed_slew_proof',
        'MountedSpeedNegative', 'shared.mounted-pose-recorder-control-v1', 'S4',
        subjects=(('stantler',234,'MOUNTED','existing'),)),
    ProofAdapter('stalker-runtime-v1','devtools_profile_feature_proof','ProfileFeatureNegative',None,
        subjects=(('gastly',92,'WILD','spawn'),),feature='stalker-runtime-v1'),
    ProofAdapter('playful-runtime-v1','devtools_profile_feature_proof','ProfileFeatureNegative',None,
        subjects=(('clefairy',35,'WILD','spawn'),('clefable',36,'WILD','spawn')),feature='playful-runtime-v1'),
    ProofAdapter('startled-runtime-v1','devtools_profile_feature_proof','ProfileFeatureNegative',None,
        subjects=(('bellsprout',69,'WILD','spawn'),),feature='startled-runtime-v1'),
    ProofAdapter('ambush-player-landing-v1','devtools_profile_feature_proof','ProfileFeatureNegative',None,'S4',
        subjects=(('weepinbell',70,'WILD','spawn'),),feature='ambush-player-landing-v1'),
    ProofAdapter('fly-in-runtime-v1','devtools_profile_feature_proof','ProfileFeatureNegative',None,'S4',
        subjects=(('pidgey',16,'WILD','spawn'),),feature='fly-in-runtime-v1'),
    ProofAdapter('waddle-runtime-v1','devtools_profile_feature_proof','ProfileFeatureNegative',None,'S4',
        subjects=(('bellsprout',69,'WILD','spawn'),),feature='waddle-runtime-v1'),
    ProofAdapter('floaty-bounce-hop-pause-v1','devtools_profile_feature_proof','ProfileFeatureNegative',None,'S4',
        subjects=(('jigglypuff',39,'WILD','spawn'),),feature='floaty-bounce-hop-pause-v1'),
    ProofAdapter('held-control-runtime-v1','devtools_profile_feature_proof','ProfileFeatureNegative',None,
        subjects=(('mankey',56,'WILD','spawn'),('rattata',19,'WILD','spawn')),feature='held-control-runtime-v1'),
    ProofAdapter('blocked-wild-facing-v1','devtools_profile_feature_proof','ProfileFeatureNegative',None,
        subjects=(('exeggcute',102,'WILD','spawn'),),feature='blocked-wild-facing-v1'),
)})


def get_adapter(kind):
    """Return an explicit adapter or None for an existing unrelated path."""
    return ADAPTERS.get(kind) if isinstance(kind,str) else None
