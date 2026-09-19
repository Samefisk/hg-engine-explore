"""Follower specialization of the bounded field-transition rebind meter."""

from tools.overworld.devtools_wild_transition_measurement import WildTransitionMeasurement


KIND = "follower-transition-rebind-v1"
REQUIREMENT = "legacy.follower-transition"


class FollowerTransitionMeasurement(WildTransitionMeasurement):
    def __init__(self, test, *, max_frames):
        super().__init__(
            test,
            max_frames=max_frames,
            kind=KIND,
            requirement=REQUIREMENT,
            subject_id="cyndaquil",
            species=155,
            role="FOLLOWER",
            acquire="existing",
        )
