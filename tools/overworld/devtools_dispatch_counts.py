"""Optional native work counts; never a replacement for CPU or frame checks."""

SCOPE = "interpreter-dispatches-not-retired-instructions"


def validate_dispatch_counts(value, *, require_complete=True):
    if not isinstance(value, dict) or set(value) != {
            "version", "enabled", "complete", "frameSequence", "arm9", "arm7", "scope"}:
        raise ValueError("invalid guest dispatch schema")
    if type(value["version"]) is not int or value["version"] != 1 or value["scope"] != SCOPE:
        raise ValueError("invalid guest dispatch version or scope")
    if type(value["enabled"]) is not bool or type(value["complete"]) is not bool:
        raise ValueError("invalid guest dispatch flags")
    for key in ("frameSequence", "arm9", "arm7"):
        if type(value[key]) is not int or not 0 <= value[key] <= 0xFFFFFFFFFFFFFFFF:
            raise ValueError("invalid guest dispatch count")
    if require_complete and (not value["enabled"] or not value["complete"] or not value["frameSequence"]):
        raise ValueError("guest dispatch frame incomplete or disabled")
    return value
