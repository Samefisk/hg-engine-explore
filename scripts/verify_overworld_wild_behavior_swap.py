#!/usr/bin/env python3
"""Focused ownership/retry model for the selector-152/validator-156 swap."""

from dataclasses import dataclass
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"


@dataclass
class State:
    selector: bool = False
    validator: bool = False
    quarantine: bool = False
    must_restore: bool = False
    attempted: bool = False
    published: bool = False


def attempt(state, *, selector_valid=True, selector_cancel=True, selector_unload=True,
            validator_load=True, callback="success", validator_unload=True,
            selector_reload=True, restored_selector_valid=True):
    state.attempted = True
    if state.validator:
        if not validator_unload:
            state.attempted = False
            return
        state.validator = False
    if state.must_restore:
        if not state.selector:
            if not selector_reload:
                state.attempted = False
                return
            state.selector = True
        if not restored_selector_valid:
            state.quarantine = True
            state.attempted = False
            return
        state.must_restore = False
    if state.quarantine:
        return
    if state.selector:
        state.must_restore = True
        if not selector_valid:
            state.quarantine = True
            return
        if not selector_cancel or not selector_unload:
            state.attempted = False
            return
        state.selector = False
    if not validator_load:
        if state.must_restore:
            if selector_reload:
                state.selector, state.must_restore = True, False
            else:
                state.attempted = False
                return
        state.attempted = False
        return
    state.validator = True
    if not validator_unload:
        if callback == "permanent":
            state.quarantine = True
        state.attempted = False
        return
    state.validator = False
    if state.must_restore:
        if not selector_reload:
            state.attempted = False
            return
        state.selector = True
        if not restored_selector_valid:
            state.quarantine = True
            return
        state.must_restore = False
    if callback == "success":
        state.published = True
    elif callback == "transient":
        state.attempted = False


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def main():
    source = SOURCE.read_text()
    for token in (
        "OWBD_OVERLAP_SELECTOR", "OWBD_OVERLAP_VALIDATOR", "OWBD_OVERLAP_QUARANTINED",
        "OWBD_OVERLAP_MUST_RESTORE", "OWBD_LOAD_TRANSIENT_FAILURE",
        "OverworldWildSpawns_RestoreFollowerSelector",
        "if (!FS_UnloadOverlay(0, OVERLAY_OVERWORLD_WILD_BEHAVIOR_VALIDATOR))",
        "if (!LoadOverlayNoInitAsync(0, OVERLAY_OVERWORLD_FOLLOWER_SELECTOR))",
    ):
        require(token in source, f"production swap contract missing: {token}")

    state = State(selector=True)
    attempt(state, selector_valid=False)
    require(state.selector and state.quarantine and not state.validator and not state.published,
            "invalid selector authentication did not quarantine resident selector")

    state = State(selector=True)
    attempt(state, callback="permanent", validator_unload=False)
    require(state.validator and state.must_restore and state.quarantine and not state.published,
            "corrupt validator plus unload failure lost overlap ownership")

    state = State(selector=True)
    attempt(state, callback="success", selector_reload=False)
    require(not state.validator and state.must_restore and not state.selector
            and not state.attempted and not state.published,
            "selector reload failure lost retry/restore obligation")

    state = State(selector=True)
    attempt(state, validator_load=False)
    require(state.selector and not state.must_restore and not state.validator and not state.published,
            "validator load failure did not restore physical selector ownership")

    state = State(selector=False, validator=True, quarantine=True, must_restore=True)
    attempt(state, validator_unload=True, restored_selector_valid=True)
    require(state.selector and not state.validator and state.quarantine and not state.must_restore,
            "quarantine prevented validator unload/selector restoration service")

    for failure in ("transient",):
        state = State()
        attempt(state, callback=failure)
        require(not state.attempted and not state.validator and not state.published,
                "transient callback failure permanently locked fallback")
    for keyword in ("validator_load",):
        state = State()
        attempt(state, **{keyword: False})
        require(not state.attempted and not state.published, "transient overlay load did not retry")

    state = State(selector=True)
    attempt(state, callback="success")
    require(state.selector and state.published and not state.validator and not state.must_restore,
            "successful swap published before selector restoration")
    print("overlay swap: 8 ownership/authentication/retry fixtures passed")


if __name__ == "__main__":
    main()
