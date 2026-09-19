"""One-way diagnostic ablation of optional spawn-detail entry readers.

Call gate at the start of NativeObservation._tap's installed entry closure,
before scope or native reads. No hook is removed. Enabling is allowed only
between operations, with no pending return callback, so omitting an entry
also omits its complete reader/return group. Both modes prohibit acceptance.
"""

LABELS = (
    "spawn-finalized", "spawn-queued", "spawn-prepared", "spawn-motion",
    "spawn-landing-height", "spawn-landing-surface", "spawn-landing-refresh-height",
)
MAX_COUNT = 0xFFFFFFFF
_CONTEXTS = ("contexts", "spawn_contexts", "finalization_contexts",
             "spawn_height_contexts", "policy_contexts", "reposition_contexts", "return_tokens")


class _SpawnCostProbe:
    def __init__(self, session, observer, mode):
        self._session, self._observer, self._mode = session, observer, mode
        self._frame, self._cycle = session.completed_frames, session.rt.EXECUTED_FRAME_COUNT
        self._counts = {label: 0 for label in LABELS}
        self._error = None

    @property
    def mode(self):
        return self._mode

    def gate(self, observer, label):
        if self._error is not None:
            raise self._error
        if observer is not self._observer:
            self._error = ValueError("spawn cost probe observer changed")
            raise self._error
        if label not in self._counts:
            return True
        if self._counts[label] == MAX_COUNT:
            self._error = ValueError("spawn cost probe counter exhausted")
            raise self._error
        self._counts[label] += 1
        return self._mode == "baseline"

    def result(self):
        omitted = self._mode == "omit-spawn-details"
        return dict(schemaVersion=1, mode=self._mode, enabledAtFrame=self._frame,
                    enabledAtNativeCycle=self._cycle, frame=self._session.completed_frames,
                    nativeCycle=self._session.rt.EXECUTED_FRAME_COUNT,
                    scope="spawn-detail-reader-cost-diagnostic",
                    counterScope="entry-dispatch-before-scope-and-code-authentication",
                    counters={label: dict(entries=count, omitted=count if omitted else 0)
                              for label, count in self._counts.items()},
                    immutable=True, hooksRetained=True, acceptanceForbidden=True,
                    acceptedProof=False, proofStatus="diagnostic-only",
                    failure=str(self._error) if self._error else None)


def enable_spawn_cost_probe(session, args):
    """Select one mode once; never write guest state or advance the emulator."""
    if type(args) is not dict or set(args) != {"mode"} or args["mode"] not in (
            "baseline", "omit-spawn-details"):
        raise ValueError("invalid spawn cost probe mode")
    if getattr(session, "spawn_cost_probe", None) is not None:
        raise ValueError("spawn cost probe is already enabled for this session")
    observer = getattr(session, "native_observation", None)
    if not getattr(session, "prepared", False) or observer is None or not observer.installed:
        raise ValueError("spawn cost probe requires prepared setup and installed observer")
    if observer.session is not session or any(label not in observer.calls for label in LABELS):
        raise ValueError("spawn cost probe observer or labels differ")
    if (getattr(session, "native_bridge_active", False)
            or getattr(session, "pending_samples", None) is not None
            or any(getattr(observer, name) for name in _CONTEXTS)):
        raise ValueError("spawn cost probe has in-flight observation work")
    if any(type(value) is not int or value < 0 for value in (
            session.completed_frames, session.rt.EXECUTED_FRAME_COUNT)):
        raise ValueError("spawn cost probe game clocks are invalid")
    session.spawn_cost_probe = _SpawnCostProbe(session, observer, args["mode"])
    return session.spawn_cost_probe.result()


def gate(observer, label):
    """True keeps the unchanged entry path; False omits only its reader work."""
    probe = getattr(observer.session, "spawn_cost_probe", None)
    return True if probe is None else probe.gate(observer, label)
