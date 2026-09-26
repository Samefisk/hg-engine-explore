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
    ProofAdapter('notice-player-runtime-v1','devtools_profile_feature_proof','ProfileFeatureNegative',None,
        subjects=(('mareep',179,'WILD','spawn'),),feature='notice-player-runtime-v1'),
    ProofAdapter('stalker-runtime-v1','devtools_profile_feature_proof','ProfileFeatureNegative',None,
        subjects=(('gastly',92,'WILD','spawn'),),feature='stalker-runtime-v1'),
    ProofAdapter('playful-runtime-v1','devtools_profile_feature_proof','ProfileFeatureNegative',None,
        subjects=(('clefairy',35,'WILD','spawn'),('clefable',36,'WILD','spawn')),feature='playful-runtime-v1'),
    ProofAdapter('startled-runtime-v1','devtools_profile_feature_proof','ProfileFeatureNegative',None,
        subjects=(('bellsprout',69,'WILD','spawn'),),feature='startled-runtime-v1'),
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
