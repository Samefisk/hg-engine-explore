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

    @property
    def module(self):
        module=import_module('tools.overworld.'+self.module_name)
        if module.KIND!=self.kind:
            raise ValueError('proof adapter kind differs: '+self.kind)
        return module

    @property
    def requirement(self):return self.module.REQUIREMENT

    @property
    def claims(self):return tuple(self.module.CLAIMS)

    @property
    def faults(self):return tuple(self.module.FAULTS)

    @property
    def is_control(self):return self.recorder_control_requirement is None

    def contract(self):return self.module.contract()

    def measurements(self,replay,record):return self.module.measurements(replay,record)

    def negative(self,fault):
        # Keep the existing constructor's fault validation and exception text.
        return getattr(self.module,self.negative_name)(fault)

    def validate_negative_result(self,result,fault):
        return self.module.validate_negative_result(result,fault)


ADAPTERS=MappingProxyType({adapter.kind:adapter for adapter in (
    ProofAdapter('diagonal-corner-v1','devtools_corner_proof','CornerNegative',
        'shared.corner-recorder-control-v1'),
    ProofAdapter('live-corner-control-v1','devtools_corner_control_proof','CornerControlNegative',None),
    ProofAdapter('mounted-frame-matrix-v1','devtools_walk_matrix_proof','MatrixNegative',
        'shared.walk-matrix-recorder-control-v1'),
    ProofAdapter('live-walk-matrix-control-v1','devtools_walk_matrix_control_proof','MatrixControlNegative',None),
    ProofAdapter('mounted-stomp-v1','devtools_stomp_proof','StompNegative',
        'shared.stomp-recorder-control-v1'),
    ProofAdapter('live-stomp-control-v1','devtools_stomp_control_proof','StompControlNegative',None),
    ProofAdapter('mounted-crash-v1','devtools_mounted_crash_proof','CrashNegative',
        'shared.crash-recorder-control-v1','S4'),
    ProofAdapter('live-crash-control-v1','devtools_mounted_crash_control_proof','CrashControlNegative',None),
    ProofAdapter('turn-skid-v1','devtools_turn_skid_proof','TurnSkidNegative',
        'shared.walk-matrix-recorder-control-v1'),
)})


def get_adapter(kind):
    """Return an explicit adapter or None for an existing unrelated path."""
    return ADAPTERS.get(kind) if isinstance(kind,str) else None
