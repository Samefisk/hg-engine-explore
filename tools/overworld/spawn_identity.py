"""Native OverworldWildSpawn identity flags, shared by live and replay readers."""


def live_spawn_flags(value):
    # active(1), OW_WILD_SPAWN_AGGRO_FLAG(2), AGGRO_PENDING_FLAG(4).
    # A flag without active, an undefined bit, or a coerced value is not proof.
    return type(value) is int and value in (1, 3, 5, 7)
