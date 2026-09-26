"""Bounded, read-only native observations shared by devtools and job checks.

These are raw call receipts, not a scenario, subject selector or verdict. Hooks
are installed before boot; code is checked on entry because overlays load later.
Completed-main-queue flush supplies the coherent game-frame label. Normal
observation is read-only. An explicit checked height-reader control owns its
same-callback native Y fault and restoration; it has no normal-play credit.
"""
from __future__ import annotations

from collections import OrderedDict, deque
from copy import deepcopy
import hashlib
from tools.overworld.devtools_spawn_cost_probe import gate as spawn_cost_gate


# Stock unk_0205FD20.s:sub_02060F24 copies current to previous, then reserves
# one cardinal next tile. This is admission, NOT rendered/terminal completion.
PLAYER_STEP_ADMISSION = 0x02060F24
PLAYER_WALK_COLLISION = 0x0205DA34
PLAYER_WALK_COLLISION_RETURN = 0x0205D4C6
SPAWN_REFRESH_HEIGHT = 0x02061070
SPAWN_CREATE_OBJECT = 0x0205E2B4  # rom_gen.ld: CreateSpecialFieldObjectWithParams
MON_APPLY_FRIENDSHIP_MOD = 0x0206FE90
FRIENDSHIP_WAIT_WINDOW = (4639, 4644)
WILD_PENDING_BATTLE_OFFSETS = {
    "personality": 252,
    "speciesAndForm": 256,
    "slot": 262,
    "mapGeneration": 948,
    "encounterGeneration": 950,
}

# Anchored by the compiled real OverworldMotionDecision enum in the probe tests.
MOTION_DECISIONS = ("ACCEPTED", "RETRY_WORLD_BUSY", "BLOCKED", "SIDE_TILE", "TERRAIN",
                    "OCCUPIED", "RESERVED", "DIRECTION", "PROFILE", "ALREADY_ACTIVE",
                    "STALE_FIELD", "CONTEXT_LOST", "NO_CANDIDATE")
CHAIN_OUTCOMES = ("RETRY", "STARTED", "COMPLETE", "ABORT")

# The shared landing classifier removes catalog-only surfaces before it falls
# back to the native metatile matcher. Canopy remains because its old topology
# locator is still the compatibility fallback when no catalog surface matches.
DESTINATION_NATIVE_TILE_MASK = ~((1 << 6) | (1 << 7) | (1 << 8) | (1 << 9)) & 0xFFFF


class NativeObservationError(ValueError):
    pass


def public_bytes(session, address, size):
    address &= 0xFFFFFFFF
    main = 0x02000000 <= address < address + size <= 0x02400000
    stack = 0x027E0000 <= address < address + size <= 0x027E3FC0
    if address & 3 or not (main or stack):
        raise NativeObservationError(f"public buffer {address:#x}+{size} is outside aligned RAM/stack")
    data = session.read(address, size)
    if len(data) != size:
        raise NativeObservationError(f"public buffer read returned {len(data)} bytes, expected {size}")
    return data


class NativeObservation:
    MAX_EVENTS = 4096
    MAX_PROFILES = 64
    MAX_DEPTH = 64
    MAX_RNG_DRAWS = 16
    MAX_SPAWN_RESOLVERS = 64
    TIMED_CALLS = frozenset(("population-frame-cost", "population-movement-cost", "population-step-cost",
                             "follower-spawn-cost", "spawn-queued", "spawn-refill-cost", "spawn-helper-cost",
                             "spawn-archive-cost", "spawn-finalized", "spawn-prepared", "spawn-motion",
                             "spawn-landing-height", "spawn-destination-search",
                             "spawn-metadata", "spawn-class-selection", "spawn-object-create",
                             "friendship-mod", "archive-open-cost", "archive-close-cost",
                             "archive-alloc-read-cost", "archive-read-cost", "archive-part-read-cost",
                             "archive-id-read-cost", "archive-id-alloc-read-cost"))

    def __init__(self, session, hooks, elf_code):
        self.session, self.hooks, self.elf_code = session, hooks, elf_code
        self.pending, self.ready = deque(), deque()
        self.profiles = OrderedDict()
        self.sequence = 0
        self.events_dropped = 0
        self.profiles_evicted = 0
        self.resolver_discovery = None
        self.contexts, self.spawn_contexts, self.policy_contexts = [], [], []
        self.spawn_queue_contexts = []
        self.spawn_queue_id = 0
        self.destination_contexts = []
        self.latest_destination_results = {}
        self.pending_destination_scans = {}
        self.finalization_contexts, self.finalizations = [], {}
        self.finalization_id = 0
        self.latest_finalization_results = {}
        self.queued_finalizations = {}
        self.reposition_contexts = []
        self.reposition_id = 0
        self.reposition_call_sites = {}
        self.caller_bounds = {}
        self.latest_finalizations = {}
        self.spawn_height_contexts, self.spawn_height_call_sites = [], {}
        self.spawn_height_trace = None
        self.tokens, self.return_tokens = [], []
        self.calls = {}
        self.installed = False
        self.player_steps_admitted = 0
        self.player_step_count = 0
        self.player_step_frame = None
        self.wait_probe = None
        self.main_loop_probe = None
        self.source_hash = hashlib.sha256(
            (session.rt.REPO / "data/overworld_behavior_profiles.json").read_bytes()).hexdigest()

    def _clock(self):
        rt, emu = self.session.rt, self.session.emu
        return {"actorFrame": rt.unsigned(emu, rt.ACTOR_DESCRIPTOR["state"]["address"] + 8),
                "nativeCycle": rt.EXECUTED_FRAME_COUNT}

    def _subject(self, slot):
        rt = self.session.rt
        if not 0 <= slot < rt.ACTOR_DESCRIPTOR["capacities"]["actors"]:
            raise NativeObservationError(f"native actor slot {slot} exceeds descriptor")
        actor = rt.actor_state(self.session.emu, slot)
        if actor.get("active") is not True:
            return {"status": "not-active", "slot": slot}
        return {"status": "observed-public-subject", "slot": slot,
                "scope": "public snapshot only; engine binding requires the coherent frame snapshot",
                **{key: deepcopy(actor[key]) for key in (
                    "handle", "species", "form", "level", "subjectIdentity", "role",
                    "behaviorFingerprint", "matchedLayerMask", "commitSequence",
                    "motionPhase", "motionKind", "authorityGeneration",
                      "engineAnchorGeneration", "presentationGeneration")}}

    def _guest_clock(self):
        value = self.session.emu.guest_clock()
        if value.get("version") != 1 or value.get("running") is not True \
                or value.get("scope") != "nds-scheduler-ticks-not-cpu-or-instructions" \
                or any(type(value.get(key)) is not int or value[key] < 0
                       for key in ("arm9Timestamp", "arm7Timestamp", "frameSequence")):
            raise NativeObservationError("spawn guest clock is not an active native callback reading")
        return dict(value)

    def _queue(self, kind, context, data):
        self.sequence += 1
        value = {"observation": kind, "sequence": self.sequence,
                 "entryActorFrame": context["entry"]["actorFrame"],
                 "entryNativeCycle": context["entry"]["nativeCycle"],
                 "returnActorFrame": context["returned"]["actorFrame"],
                 "returnNativeCycle": context["returned"]["nativeCycle"],
                 "setupMode": context["setupMode"], "returnValue": context["returnValue"],
                 **data}
        if "guestEntry" in context:
            start, end = context["guestEntry"], context["guestReturn"]
            if any(end[key] < start[key] for key in ("arm9Timestamp", "frameSequence")):
                raise NativeObservationError("spawn guest clock moved backwards during a call")
            value["guestTiming"] = {
                "scope": "inclusive-arm9-scheduler-ticks-including-waits-and-irqs",
                "entry": start, "returned": end,
                "arm9Ticks": end["arm9Timestamp"] - start["arm9Timestamp"]}
        if len(self.pending) >= self.MAX_EVENTS:
            self.pending.popleft()
            self.events_dropped += 1
        self.pending.append(value)
        if kind == "spawn-finalized" and value["pairEligible"]:
            # Store the actual framed-event data, including its unique sequence.
            # At most one unconsumed value per wild slot can exist.
            self.finalizations[value["slot"]] = deepcopy(value)
        if kind == "spawn-landing-height":
            parent = self.spawn_contexts[-1]
            jump = parent.get("_activeSpawnJump")
            if jump is None:
                parent["initialLandingHeight"] = deepcopy(value)
            else:
                jump["landingHeight"] = deepcopy(value)

    def _tap(self, label, address, expected, before, after, scope=None, *, resident=False):
        address &= ~1
        if len(expected) != 32:
            raise NativeObservationError(f"{label} has no complete packaged entry identity")
        # Require the expected linked/stock body to exist in this exact ROM,
        # even though its overlay may not yet be resident at installation.
        if not any(base <= address and address + 32 <= base + len(data)
                   and data[address - base:address - base + 32] == expected
                   for base, data in self.session.code_regions):
            raise NativeObservationError(f"{label} linked entry differs from the packaged ROM")
        self.calls[label] = {"address": address, "entrySha256": hashlib.sha256(expected).hexdigest(),
                             "entered": 0, "returned": 0, "nonmatchingEntries": 0}

        def entry():
            if not spawn_cost_gate(self, label):
                return
            if scope is not None and not scope():
                return
            if self.session.read(address, 32) != expected:
                self.calls[label]["nonmatchingEntries"] += 1
                if resident:
                    raise NativeObservationError(f"{label} resident code identity differs")
                return  # Another overlay can legitimately occupy this address.
            if len(self.contexts) >= self.MAX_DEPTH:
                raise NativeObservationError("native observation nesting limit reached")
            data = before()
            if data is None:
                return
            registers = self.session.emu.memory.register_arm9
            context = {"entry": self._clock(), "setupMode": "prepared" if self.session.prepared else "normal",
                       "data": data, "sp": registers.sp & 0xFFFFFFFF}
            if label in self.TIMED_CALLS or (label == "behavior-resolved"
                    and (self.finalization_contexts or self.spawn_contexts)):
                context["guestEntry"] = self._guest_clock()
            self.calls[label]["entered"] += 1
            self.contexts.append(context)
            token = None

            def returned():
                if registers.sp & 0xFFFFFFFF != context["sp"]:
                    return
                self.hooks.remove(token)
                self.return_tokens.remove(token)
                self.contexts.remove(context)
                if self.session.read(address, 32) != expected:
                    raise NativeObservationError(f"{label} lost code identity before return")
                context.update(returned=self._clock(), returnValue=registers.r0 & 0xFFFFFFFF)
                if "guestEntry" in context:
                    context["guestReturn"] = self._guest_clock()
                self.calls[label]["returned"] += 1
                result = after(data, context)
                if result is not None:
                    self._queue(label, context, result)

            token = self.hooks.add(registers.lr, returned)
            self.return_tokens.append(token)
            if label == "chain-prepared-start":
                control = getattr(self.session, "chain_retry_control", None)
                if control is not None:
                    try:
                        control.start(data, context, address)
                    except Exception as error:
                        control.failure = control.failure or str(error)
                        raise

        self.tokens.append(self.hooks.add(address, entry))

    def install(self):
        if self.installed:
            raise NativeObservationError("native observer is already installed")
        rt = self.session.rt
        actor_file = rt.REPO / "build/overworld_actor_system_overlay_linked.o"
        wild_file = rt.REPO / "build/overworld_wild_spawns_overlay_linked.o"
        actor_symbols = rt.linked_symbols(actor_file)
        self.chain_actor_symbols = actor_symbols
        rt.ACTOR_SYMBOLS = actor_symbols

        def linked(label, path, symbols, name, before, after, *, scope=None, resident=False):
            address = rt.linked_symbol(symbols, name) & ~1
            self._tap(label, address, self.elf_code(path, address, 32), before, after, scope=scope, resident=resident)

        from tools.overworld.devtools_role_profile import install_role_profiles
        self.role_profiles = install_role_profiles(self, linked)
        from tools.overworld.devtools_binding_context import install_binding_context
        self.binding_context = install_binding_context(self, linked)

        linked("spawn-finalized", wild_file, rt.WILD_SYMBOLS,
               "OverworldWildSpawns_FinalizePreparedSpawn", self._finalize_before, self._finalize_after)
        linked("spawn-queued", wild_file, rt.WILD_SYMBOLS,
               "OverworldWildSpawns_SpawnOne", self._spawn_queue_before, self._spawn_queue_after)
        linked("wild-battle-request", wild_file, rt.WILD_SYMBOLS,
               "OverworldWildSpawns_RequestBattleScript",
               self._battle_request_before, self._battle_request_after)
        cost_scope = lambda: getattr(getattr(self.session, "spawn_cost_probe", None), "mode", None) == "baseline"
        helper_file = rt.REPO / "build/overworld_wild_helper_overlay_linked.o"
        helper_symbols = rt.linked_symbols(helper_file)
        for label, path, symbols, name in (
                ("population-frame-cost", wild_file, rt.WILD_SYMBOLS, "OverworldWildSpawns_FrameMovementTask"),
                ("population-movement-cost", wild_file, rt.WILD_SYMBOLS, "OverworldWildSpawns_TickMovementParams.constprop.0"),
                ("population-step-cost", wild_file, rt.WILD_SYMBOLS, "OverworldWildSpawns_OverlayOnPlayerStep"),
                ("follower-spawn-cost", wild_file, rt.WILD_SYMBOLS, "OverworldWildSpawns_TrySpawnFollower"),
                ("spawn-refill-cost", wild_file, rt.WILD_SYMBOLS, "OverworldWildSpawns_TryRefill"),
                ("spawn-helper-cost", helper_file, helper_symbols, "OverworldWildHelper_TryPrepareSpawn"),
                ("spawn-archive-cost", wild_file, rt.WILD_SYMBOLS, "OverworldWildSpawns_HelperLoadArchiveData")):
            linked(label, path, symbols, name, self._refill_cost_before,
                   self._refill_cost_after, scope=cost_scope)
        linked("spawn-destination-search", wild_file, rt.WILD_SYMBOLS,
               "OverworldWildSpawns_TryPickSpawnDestinationMask", self._destination_before,
               self._destination_after, scope=lambda: bool(self.finalization_contexts))
        spawn_scope = lambda: bool(self.finalization_contexts or self.spawn_contexts)
        metadata_file = rt.REPO / "build/overworld_wild_behavior_data_overlay_linked.o"
        linked("spawn-metadata", metadata_file, rt.linked_symbols(metadata_file),
               "OverworldWildBehavior_TryGetSpawnMetadata", self._spawn_cost_before,
               self._spawn_cost_after, scope=spawn_scope)
        linked("spawn-class-selection", actor_file, actor_symbols,
               "BehaviorResolver_InspectClass", self._spawn_cost_before,
               self._spawn_cost_after, scope=spawn_scope)
        linked("spawn-prepared", wild_file, rt.WILD_SYMBOLS,
               "OverworldWildSpawns_SpawnPreparedEncounter", self._spawn_before, self._spawn_after)
        linked("spawn-motion", wild_file, rt.WILD_SYMBOLS,
               "OverworldWildSpawns_StartPreparedCustomJumpCommand", self._jump_before, self._jump_after)
        linked("spawn-landing-height", wild_file, rt.WILD_SYMBOLS,
               "OverworldWildSpawns_ResolveObjectLandingHeight", self._spawn_height_before, self._spawn_height_after,
               scope=lambda: bool(self.spawn_contexts))
        linked("spawn-landing-surface", wild_file, rt.WILD_SYMBOLS,
               "OverworldWildSpawns_QuerySurface", self._spawn_surface_before, self._spawn_height_detail_after,
               scope=lambda: bool(self.spawn_height_contexts))
        linked("behavior-resolved", actor_file, actor_symbols,
               "BehaviorResolver_Resolve", self._resolver_before, self._resolver_after)
        linked("walk-policy", actor_file, actor_symbols,
               "ActorSystem_ReduceWalk", self._policy_before, self._policy_after)
        linked("chain-reposition-attempt", wild_file, rt.WILD_SYMBOLS,
               "OverworldWildSpawns_RunChainReposition", self._reposition_before, self._reposition_after)
        # Separate taps preserve the existing spawn-motion receipt and scope.
        linked("chain-landing", wild_file, rt.WILD_SYMBOLS,
               "OverworldWildSpawns_ClassifyBehaviorHopLandingTile", self._landing_before, self._landing_after,
               scope=lambda: bool(self.reposition_contexts))
        linked("chain-prepared-start", wild_file, rt.WILD_SYMBOLS,
               "OverworldWildSpawns_StartPreparedCustomJumpCommandTimed", self._chain_start_before, self._chain_start_after,
               scope=lambda: bool(self.reposition_contexts))
        runtime_file = rt.REPO / "build/overworld_wild_runtime_overlay_linked.o"
        linked("chain-motion-request", runtime_file, rt.linked_symbols(runtime_file),
               "OverworldWildRuntime_RequestMotion", self._chain_request_before, self._chain_request_after,
               scope=lambda: bool(self.reposition_contexts))
        task6_file = rt.REPO / "build/pokemon_move_history_task6_overlay_linked.o"
        linked("chain-hop-plan", task6_file, rt.linked_symbols(task6_file),
               "OverworldActorHopPlanner_Plan", self._chain_plan_before, self._chain_plan_after,
               scope=lambda: bool(self.reposition_contexts)
               and self.reposition_contexts[-1]["_activeStart"] is not None)
        for label, name in (("surface", "QuerySurface"), ("terrain", "DoesAllowedTileMatch"),
                            ("objects", "IsTileOccupiedByObject"),
                            ("nonplayer", "IsTileOccupiedByNonPlayerObject"),
                            ("surface-occupancy", "IsTileOccupiedOnSurface")):
            before = (self._allowed_tile_before if label == "terrain"
                      else lambda kind=label: self._landing_detail_before(kind))
            after = self._allowed_tile_after if label == "terrain" else self._landing_detail_after
            scope = ((lambda: bool(self.destination_contexts) or self._landing_detail_scope())
                     if label == "terrain" else self._landing_detail_scope)
            linked("chain-landing-" + label, wild_file, rt.WILD_SYMBOLS,
                   "OverworldWildSpawns_" + name,
                   before, after, scope=scope, resident=True)
        # rom_gen.ld / vanilla GF_Rand: observe returns only while a relevant
        # public policy call owns the draw. Never call or alter the RNG.
        address = 0x0201FD44
        stock = (rt.REPO / "base/arm9.bin").read_bytes()
        # Named retail filesystem.c entries, checked against this packaged ROM.
        # Observe all callers: map-object assets can load after SpawnOne returns.
        # Arguments are raw API registers; do not guess a NARC id from a handle.
        for label, address in (("archive-open-cost", 0x02007688),
                               ("archive-close-cost", 0x0200770C),
                               ("archive-alloc-read-cost", 0x0200771C),
                               ("archive-read-cost", 0x0200778C),
                               ("archive-part-read-cost", 0x0200782C),
                               ("archive-id-read-cost", 0x02007508),
                               ("archive-id-alloc-read-cost", 0x02007524)):
            self._tap(label, address, stock[address - 0x02000000:address - 0x02000000 + 32],
                      self._archive_cost_before, self._archive_cost_after,
                      scope=cost_scope, resident=True)
        address = 0x0201FD44
        self._tap("friendship-mod", MON_APPLY_FRIENDSHIP_MOD,
                  stock[MON_APPLY_FRIENDSHIP_MOD - 0x02000000:
                       MON_APPLY_FRIENDSHIP_MOD - 0x02000000 + 32],
                  self._friendship_before, self._friendship_after,
                  scope=self._friendship_scope, resident=True)
        self._tap("spawn-object-create", SPAWN_CREATE_OBJECT,
                  stock[SPAWN_CREATE_OBJECT - 0x02000000:SPAWN_CREATE_OBJECT - 0x02000000 + 32],
                  self._spawn_cost_before, self._spawn_cost_after, scope=spawn_scope, resident=True)
        self._tap("spawn-landing-refresh-height", SPAWN_REFRESH_HEIGHT,
                  stock[SPAWN_REFRESH_HEIGHT - 0x02000000:SPAWN_REFRESH_HEIGHT - 0x02000000 + 32],
                  self._spawn_refresh_before, self._spawn_height_detail_after,
                  scope=lambda: bool(self.spawn_height_contexts), resident=True)
        self._tap("walk-rng", address, stock[address - 0x02000000:address - 0x02000000 + 32],
                  lambda: self.policy_contexts[-1], self._rng_after,
                  scope=lambda: bool(self.policy_contexts))
        address = PLAYER_STEP_ADMISSION
        self._tap("player-step-admitted", address,
                  stock[address - 0x02000000:address - 0x02000000 + 32],
                  self._player_step_before, self._player_step_after, resident=True)
        address = PLAYER_WALK_COLLISION
        self._install_player_collision_identity(stock)
        self._tap("player-collision", address,
                  stock[address - 0x02000000:address - 0x02000000 + 32],
                  self._player_collision_before, self._player_collision_after,
                  scope=lambda: self.session.emu.memory.register_arm9.lr & ~1 == PLAYER_WALK_COLLISION_RETURN,
                  resident=True)
        self.installed = True

    def _battle_current(self, slot):
        from tools.overworld.devtools_runtime import actor_identity_checks
        rt, emu = self.session.rt, self.session.emu
        actor = rt.actor_state(emu, slot)
        source = rt.wild_spawn(emu, slot)
        engine = rt.live_wild_object_identity(emu, slot)
        context = {"fieldEpoch": rt.unsigned(
                       emu, rt.ACTOR_DESCRIPTOR["state"]["address"] + 12, 2),
                   "mapGeneration": rt.unsigned(
                       emu, rt.ACTOR_DESCRIPTOR["state"]["address"] + 46, 2),
                   "mapId": rt.field_map_id(emu)}
        checks = actor_identity_checks(actor, source, engine, context, slot)
        checks.update(active=actor.get("active") is True,
                      role=actor.get("role") == "WILD")
        if not all(checks.values()):
            raise NativeObservationError("battle native identity differs: " + ", ".join(
                name for name, passed in checks.items() if not passed))
        actor.update(identityVerified=True, identityChecks=checks,
                     identityFailures=[], sourceIdentity=source,
                     engineIdentity=engine)
        if engine.get("in_manager"):
            actor["engineObject"] = rt.object_state(emu, engine["pointer"])
        return self._subject(slot), actor, source, context

    def _battle_request_before(self):
        rt, emu = self.session.rt, self.session.emu
        regs = emu.memory.register_arm9
        field, state, slot = (getattr(regs, key) & 0xFFFFFFFF
                              for key in ("r0", "r1", "r2"))
        current_field = rt.unsigned(emu, rt.G_FIELD_SYS_PTR)
        if (not current_field or field != current_field or state != rt.WILD_STATE
                or slot >= 6):
            raise NativeObservationError("battle request arguments differ")
        key_input = rt.unsigned(emu, 0x04000130, 2)
        xy_keys = rt.unsigned(emu, 0x027FFFA8, 2)
        return {
            "fieldPointer": field,
            "statePointer": state,
            "slot": slot,
            "input": {
                "heldKeys": rt.unsigned(emu, 0x021D1150),
                "newKeys": rt.unsigned(emu, 0x021D1154),
                "rawHeld": rt.unsigned(emu, 0x021D1144),
                "rawNew": rt.unsigned(emu, 0x021D1148),
                "simulatedKeys": rt.unsigned(emu, 0x021D1168),
                "physicalPressed": ((key_input | xy_keys) ^ 0x2FFF) & 0x2FFF,
            },
        }

    def _battle_request_after(self, value, context):
        if context["returnValue"] not in (0, 1):
            raise NativeObservationError("battle request BOOL result differs")
        if context["returnValue"] == 0:
            return None
        rt, emu = self.session.rt, self.session.emu
        state = value["statePointer"]
        offsets = WILD_PENDING_BATTLE_OFFSETS
        pending_slot = rt.unsigned(emu, state + offsets["slot"], 1)
        pending_slot = pending_slot - 256 if pending_slot & 0x80 else pending_slot
        if not 0 <= pending_slot < 6:
            raise NativeObservationError("battle pending slot differs")
        if pending_slot != value["slot"]:
            raise NativeObservationError("battle requested slot differs")
        subject, actor, source, context_value = self._battle_current(pending_slot)
        encoded_species = rt.unsigned(emu, state + offsets["speciesAndForm"], 2)
        pending = {
            "slot": pending_slot,
            "species": encoded_species & ((1 << 11) - 1),
            "personality": rt.unsigned(emu, state + offsets["personality"]),
            "encounterGeneration": rt.unsigned(
                emu, state + offsets["encounterGeneration"], 2),
        }
        pending_map_generation = rt.unsigned(
            emu, state + offsets["mapGeneration"], 2)
        if (pending != {"slot": pending_slot, "species": source["species"],
                        "personality": source["personality"],
                        "encounterGeneration": source["encounter_generation"]}
                or encoded_species >> 11 != source["form"]
                or pending_map_generation != context_value["mapGeneration"]):
            raise NativeObservationError("battle pending identity differs")
        return {
            "subject": subject,
            "currentActor": actor,
            "pending": pending,
            "player": rt.object_state(emu, rt.player_ptr(emu)),
            "input": value["input"],
        }

    def _chain_current(self, slot):
        # Reuse the same binding checks as coherent session inspection. This
        # native receipt retains its own clocks; it is not a rendered frame.
        from tools.overworld.devtools_runtime import actor_identity_checks
        rt, emu = self.session.rt, self.session.emu
        subject = self._subject(slot)
        actor = rt.actor_state(emu, slot)
        source = rt.wild_spawn(emu, slot)
        engine = rt.live_wild_object_identity(emu, slot)
        world = self._world_context()
        checks = actor_identity_checks(actor, source, engine, world, slot)
        lookup = engine.get("id_lookup", {})
        checks.update(active=actor.get("active") is True, role=actor.get("role") == "WILD",
                      pointer=source.get("object") == engine.get("pointer"),
                      form=actor.get("form") == source.get("form"),
                      level=actor.get("level") == source.get("level"),
                      lookup=lookup.get("status") == "complete" and lookup.get("pointer_matches") is True
                             and lookup.get("eligible_count") == 1)
        if not all(checks.values()):
            raise NativeObservationError("chain native identity differs: " + ", ".join(
                name for name, passed in checks.items() if not passed))
        return subject, source, engine, world

    @staticmethod
    def _chain_identity(subject):
        return {key: subject.get(key) for key in (
            "status", "handle", "species", "form", "level", "subjectIdentity", "role",
            "authorityGeneration", "engineAnchorGeneration", "presentationGeneration")}

    def _chain_check(self, parent, *, full=False):
        if not any(item is parent for item in self.reposition_contexts):
            raise NativeObservationError("chain child lost its owning attempt")
        rt, emu = self.session.rt, self.session.emu
        if full:
            subject, source, engine, world = self._chain_current(parent["slot"])
            if any(engine.get(key) != parent["engineIdentity"].get(key) for key in
                   ("pointer", "current_manager", "manager_index", "object_manager")):
                raise NativeObservationError("chain native object binding changed")
        else:
            # One full manager scan at each outer boundary. Child callbacks
            # recheck the actual public handle, source row and field context.
            subject = self._subject(parent["slot"])
            source = rt.wild_spawn(emu, parent["slot"])
            world = self._world_context()
        if (self._chain_identity(subject) != self._chain_identity(parent["publicSubject"])
                or source != parent["sourceIdentity"] or world != parent["worldContext"]):
            raise NativeObservationError("chain child subject or world identity changed")
        return subject

    def _chain_caller(self, name, *, actor=False, cache=None, target=None):
        """Authenticate this caller's BL/BLX, without pinning ROM addresses."""
        rt, regs = self.session.rt, self.session.emu.memory.register_arm9
        symbols = self.chain_actor_symbols if actor else rt.WILD_SYMBOLS
        path = rt.REPO / ("build/overworld_actor_system_overlay_linked.o" if actor
                          else "build/overworld_wild_spawns_overlay_linked.o")
        start = rt.linked_symbol(symbols, name) & ~1
        # Linked symbols are fixed host inputs for this observer. Do not scan
        # the whole ELF symbol table for every intermediate height seed.
        # A replaced table gets its own bound; live BL bytes are still checked
        # on every call below, including after field/overlay changes.
        key = (actor, name)
        bound = self.caller_bounds.get(key)
        if bound is None or bound[0] is not symbols or bound[1] != start:
            ends = [value & ~1 for value in symbols.values() if value & ~1 > start]
            bound = (symbols, start, min(ends) if ends else None)
            self.caller_bounds[key] = bound
        returned = regs.lr & 0xFFFFFFFE
        if bound[2] is None or not start <= returned - 2 < returned <= bound[2]:
            raise NativeObservationError("chain callback has the wrong native caller")
        cache = self.reposition_call_sites if cache is None else cache
        address = returned - 4
        if address not in cache and returned - 2 not in cache:
            if len(cache) >= 16:
                raise NativeObservationError("chain native caller-site limit reached")
            expected = self.elf_code(path, address, 4)
            first, second = (int.from_bytes(expected[n:n + 2], "little") for n in (0, 2))
            if (len(expected) == 4 and first & 0xF800 == 0xF000
                    and second & 0xF800 == 0xF800):
                size = 4
            else:
                address = returned - 2
                expected = self.elf_code(path, address, 2)
                instruction = int.from_bytes(expected, "little")
                register = (instruction >> 3) & 0xF
                if (len(expected) != 2 or instruction & 0xFF87 != 0x4780
                        or target is None or register > 12
                        or (getattr(regs, f"r{register}") & 0xFFFFFFFE)
                            != (target & 0xFFFFFFFE)):
                    raise NativeObservationError("chain caller is not an authenticated Thumb BL/BLX")
                size = 2
            if not any(base <= address and address + size <= base + len(data)
                    and data[address - base:address - base + size] == expected
                    for base, data in self.session.code_regions):
                raise NativeObservationError("chain caller differs from packaged ELF")
            cache[address] = expected
        else:
            address = address if address in cache else returned - 2
        if len(cache[address]) == 2:
            instruction = int.from_bytes(cache[address], "little")
            register = (instruction >> 3) & 0xF
            if (target is None or register > 12
                    or (getattr(regs, f"r{register}") & 0xFFFFFFFE)
                        != (target & 0xFFFFFFFE)):
                raise NativeObservationError("chain BLX target differs")
        if self.session.read(address, len(cache[address])) != cache[address]:
            raise NativeObservationError("chain caller live code differs")

    def _chain_words(self, count):
        data = public_bytes(self.session, self.session.emu.memory.register_arm9.sp & 0xFFFFFFFF, count * 4)
        return [int.from_bytes(data[n:n + 4], "little") for n in range(0, len(data), 4)]

    def _chain_bytes(self, pointer, size):
        offset = pointer & 3
        return public_bytes(self.session, pointer & ~3, (offset + size + 3) & ~3)[offset:offset + size]

    @staticmethod
    def _chain_signed(value):
        return value - 0x100000000 if value & 0x80000000 else value

    @staticmethod
    def _chain_result(record, context, *, boolean=True):
        result = context["returnValue"]
        if boolean and result not in (0, 1):
            raise NativeObservationError("chain native BOOL result differs")
        record.update(returnValue=result, entry=deepcopy(context["entry"]),
                      returned=deepcopy(context["returned"]))

    def _reposition_before(self):
        regs = self.session.emu.memory.register_arm9
        state, slot, profile, encoded = (getattr(regs, key) & 0xFFFFFFFF for key in ("r0", "r1", "r2", "r3"))
        if state != self.session.rt.WILD_STATE or encoded > 255 or profile & 3:
            raise NativeObservationError("chain Run arguments differ")
        result_pointer = self._chain_words(1)[0]
        subject, source, engine, world = self._chain_current(slot)
        origin = self.session.rt.object_state(self.session.emu, source["object"])
        if any(item["slot"] == slot for item in self.reposition_contexts):
            raise NativeObservationError("chain attempt reentered its current actor")
        self.reposition_id += 1
        value = {"attemptId": self.reposition_id, "slot": slot, "statePointer": state,
                 "observationVersion": 2,
                 "profilePointer": profile, "encodedRemaining": encoded, "worldContext": world,
                 "resultPointer": result_pointer,
                 "publicSubject": subject, "sourceIdentity": source, "engineIdentity": engine,
                 "nativeOrigin": [origin["x"], origin["y"]],
                 "landings": [], "preparedStarts": [], "_activeLanding": None, "_activeStart": None}
        self.reposition_contexts.append(value)
        return value

    def _reposition_after(self, value, context):
        after = self._chain_check(value, full=True)
        native = self.session.rt.actor_state(self.session.emu, value["slot"])
        engine = self.session.rt.object_state(self.session.emu, value["sourceIdentity"]["object"])
        control = {key: native[key] for key in ("inputOwnership", "reservationId", "motionPhase", "motionKind")}
        control["engineFlags"] = engine["flags"]
        if value["_activeLanding"] is not None or value["_activeStart"] is not None:
            raise NativeObservationError("chain attempt returned with missing child return")
        starts = value["preparedStarts"]
        value["resultHex"] = self._chain_bytes(value["resultPointer"], 4).hex()
        raw = bytes.fromhex(value["resultHex"])
        if raw[2] >= len(CHAIN_OUTCOMES) or raw[3] >= len(MOTION_DECISIONS):
            raise NativeObservationError("chain result enum differs")
        value["nativeResult"] = {"encodedRemaining": raw[0],
            "gridDelta": int.from_bytes(raw[1:2], "little", signed=True),
            "outcome": raw[2], "outcomeName": CHAIN_OUTCOMES[raw[2]],
            "reason": raw[3], "reasonName": MOTION_DECISIONS[raw[3]]}
        accepted = [item for item in starts if item["accepted"]]
        if (len(accepted) > 1 or accepted and accepted[0] is not starts[-1]
                or context["returnValue"] not in (0, 1)
                or bool(context["returnValue"]) != bool(accepted)):
            raise NativeObservationError("chain Run/start results disagree")
        if (bool(accepted) != (raw[2] == 1) or raw[2] == 1 and raw[3] != 0
                or raw[2] == 0 and raw[0] != value["encodedRemaining"]
                or raw[2] == 2 and (raw[3] != 0 or value["landings"] or starts)
                or raw[2] == 3 and raw[3] != 12):
            raise NativeObservationError("chain native outcome disagrees with start/retry")
        if {item["landingIndex"] for item in starts} != {
                item["index"] for item in value["landings"] if item["accepted"]}:
            raise NativeObservationError("accepted chain landing has no start receipt")
        if starts:
            stage = ("started" if accepted else "motion-request-rejected"
                     if starts[-1]["motionRequests"] else "prepared-before-request-rejected")
        elif value["landings"]:
            if any(item["accepted"] for item in value["landings"]):
                raise NativeObservationError("accepted chain landing has no start receipt")
            stage = "landing-search-exhausted"
        else:
            stage = "no-candidate-check"
        self.reposition_contexts.remove(value)
        return {**{key: item for key, item in value.items() if not key.startswith("_")},
                "publicSubjectAfter": after, "nativeControlAfter": control, "outcomeStage": stage}

    def _landing_before(self):
        if not self.reposition_contexts:
            return None
        parent = self.reposition_contexts[-1]
        # Ignore recursive trajectory/side-tile checks; only Run's direct
        # candidate checks belong to this eight-candidate search receipt.
        if parent["_activeStart"] is not None or parent["_activeLanding"] is not None:
            return None
        self._chain_caller("OverworldWildSpawns_RunChainReposition")
        self._chain_check(parent)
        regs = self.session.emu.memory.register_arm9
        args = [getattr(regs, key) & 0xFFFFFFFF for key in ("r0", "r1", "r2", "r3")]
        if args[:3] != [parent["statePointer"], parent["slot"], parent["worldContext"]["fieldPointer"]] or args[3] > 65535:
            raise NativeObservationError("chain landing arguments do not match attempt")
        if len(parent["landings"]) >= 8 or any(item["accepted"] for item in parent["preparedStarts"]):
            raise NativeObservationError("chain landing count/order differs")
        coords = list(map(self._chain_signed, self._chain_words(4)))
        record = {"index": len(parent["landings"]), "allowedMask": args[3],
                  "target": coords[:2], "finalTarget": coords[2:],
                  "surfaceQueries": [], "terrainMatches": [], "occupancyQueries": [],
                  "_activeDetail": None}
        record["origin"] = list(parent["nativeOrigin"])
        parent["landings"].append(record)
        parent["_activeLanding"] = record
        return {"parent": parent, "record": record}

    def _landing_after(self, value, context):
        parent, record = value["parent"], value["record"]
        self._chain_check(parent)
        if parent["_activeLanding"] is not record:
            raise NativeObservationError("chain landing return lost its parent")
        if record["_activeDetail"] is not None:
            raise NativeObservationError("chain landing has missing detail return")
        if (record["surfaceQueries"] and record["surfaceQueries"][0]["returnValue"] == 0
                and not record["terrainMatches"]):
            raise NativeObservationError("chain landing has missing terrain match receipt")
        self._chain_result(record, context, boolean=False)
        decision = context["returnValue"]
        if not 0 <= decision < len(MOTION_DECISIONS):
            raise NativeObservationError("chain landing decision enum differs")
        record.update(decision=decision, decisionName=MOTION_DECISIONS[decision], accepted=decision == 0)
        occupancy = record["occupancyQueries"]
        if occupancy:
            if decision != (5 if occupancy[0]["returnValue"] else 0):
                raise NativeObservationError("chain landing/occupancy results disagree")
            stage = "occupied" if occupancy[0]["returnValue"] else "accepted"
        elif record["accepted"]:
            raise NativeObservationError("accepted chain landing has no occupancy receipt")
        elif record["terrainMatches"] and not record["terrainMatches"][0]["returnValue"]:
            if decision != 4:
                raise NativeObservationError("chain landing/terrain results disagree")
            stage = "terrain-permission-rejected"
        elif record["surfaceQueries"]:
            stage = "surface-validation-rejected"
        else:
            stage = "pre-terrain-rejected"
        record["rejectionStage"] = stage
        record["reasonScope"] = "native call stage only; unobserved grid/policy and surface permission branches remain unknown"
        del record["_activeDetail"]
        parent["_activeLanding"] = None

    def _landing_detail_scope(self):
        if not self.reposition_contexts:
            return False
        landing = self.reposition_contexts[-1]["_activeLanding"]
        return landing is not None and landing["_activeDetail"] is None

    def _landing_detail_before(self, kind):
        parent = self.reposition_contexts[-1]
        landing = parent["_activeLanding"]
        self._chain_caller("OverworldWildSpawns_ClassifyBehaviorHopLandingTile")
        self._chain_check(parent)
        regs = self.session.emu.memory.register_arm9
        args = [getattr(regs, key) & 0xFFFFFFFF for key in ("r0", "r1", "r2", "r3")]
        if args[0] != parent["worldContext"]["fieldPointer"]:
            raise NativeObservationError("chain landing detail field differs")
        record = {"kind": kind}
        if kind == "surface":
            rows = landing["surfaceQueries"]
            target = landing["target"] if not rows else landing["origin"]
            point = list(map(self._chain_signed, args[1:3]))
            if (len(rows) >= 2 or landing["terrainMatches"] or landing["occupancyQueries"]
                    or rows and not rows[0].get("returnValue")):
                raise NativeObservationError("chain surface query count/order differs")
            record.update(point=point, pointRole="target" if not rows else "source", outputPointer=args[3])
        elif kind == "terrain":
            rows = landing["terrainMatches"]
            target = landing["target"]
            point = [self._chain_signed(args[3]), self._chain_signed(self._chain_words(1)[0])]
            surfaces = landing["surfaceQueries"]
            if rows or len(surfaces) != 1 or surfaces[0].get("returnValue") != 0 or landing["occupancyQueries"]:
                raise NativeObservationError("chain terrain match count/order differs")
            if args[1] > 65535 or args[2] > 255:
                raise NativeObservationError("chain terrain match arguments differ")
            record.update(point=point, allowedMask=args[1], behavior=args[2])
        else:
            rows = landing["occupancyQueries"]
            target = landing["target"]
            if rows or not landing["surfaceQueries"] or (landing["terrainMatches"]
                    and landing["terrainMatches"][0].get("returnValue") != 1) or (
                    landing["surfaceQueries"] and landing["surfaceQueries"][0].get("returnValue") == 0
                    and not landing["terrainMatches"]):
                raise NativeObservationError("chain occupancy query count/order differs")
            if kind == "objects":
                point = list(map(self._chain_signed, args[1:3]))
            else:
                if args[1] != parent["sourceIdentity"]["object"]:
                    raise NativeObservationError("chain occupancy ignored object differs")
                record["ignoredObject"] = args[1]
                if kind == "nonplayer":
                    point = list(map(self._chain_signed, args[2:4]))
                else:
                    words = self._chain_words(2)
                    if args[2] not in (0, 1):
                        raise NativeObservationError("chain occupancy includePlayer differs")
                    point = [self._chain_signed(args[3]), self._chain_signed(words[0])]
                    record.update(includePlayer=bool(args[2]), targetBaseY=self._chain_signed(words[1]))
                    hit = landing["surfaceQueries"][0].get("hit")
                    if hit is None or hit["height"] != record["targetBaseY"]:
                        raise NativeObservationError("chain occupancy surface height differs")
            record["point"] = point
        if point != target:
            raise NativeObservationError("chain landing detail point differs")
        rows.append(record)
        landing["_activeDetail"] = record
        return {"parent": parent, "landing": landing, "record": record}

    def _landing_detail_after(self, value, context):
        parent, landing, record = value["parent"], value["landing"], value["record"]
        self._chain_check(parent)
        if parent["_activeLanding"] is not landing or landing["_activeDetail"] is not record:
            raise NativeObservationError("chain landing detail return lost its parent")
        self._chain_result(record, context)
        if record["kind"] == "surface":
            record["hit"] = None  # FALSE does not initialize the output hit.
            if record["returnValue"]:
                raw = public_bytes(self.session, record["outputPointer"], 8)
                record["hit"] = {"height": int.from_bytes(raw[:4], "little", signed=True),
                                 "surfaceId": int.from_bytes(raw[4:6], "little"),
                                 "surfaceType": raw[6], "nodeId": raw[7], "rawHex": raw.hex()}
        landing["_activeDetail"] = None

    def _chain_start_before(self):
        if not self.reposition_contexts:
            return None
        parent = self.reposition_contexts[-1]
        self._chain_caller("OverworldWildSpawns_RunChainReposition")
        self._chain_check(parent)
        regs = self.session.emu.memory.register_arm9
        args = [getattr(regs, key) & 0xFFFFFFFF for key in ("r0", "r1", "r2", "r3")]
        words = self._chain_words(7)
        target = list(map(self._chain_signed, words[2:4]))
        if (args != [parent["statePointer"], parent["worldContext"]["fieldPointer"], parent["slot"], parent["sourceIdentity"]["object"]]
                or words[4] != parent["profilePointer"] or words[0] > 7 or words[1] > 255
                or words[5] != 1 or words[6] != 0):
            raise NativeObservationError("chain prepared start arguments do not match attempt")
        if (parent["_activeLanding"] is not None or parent["_activeStart"] is not None
                or len(parent["preparedStarts"]) >= 8 or not parent["landings"]
                or any(item["landingIndex"] == parent["landings"][-1]["index"] for item in parent["preparedStarts"])
                or any(item["accepted"] for item in parent["preparedStarts"])
                or parent["landings"][-1].get("accepted") is not True or parent["landings"][-1]["target"] != target):
            raise NativeObservationError("chain start has no matching accepted landing")
        record = {"landingIndex": parent["landings"][-1]["index"], "objectPointer": args[3],
                  "direction": words[0], "distance": words[1], "target": target,
                  "engineFlagsAtEntry": self.session.rt.object_state(self.session.emu, args[3])["flags"],
                  "profilePointer": words[4], "motionRequests": [], "_activeRequest": None,
                  "hopPlans": [], "_activePlan": None}
        parent["preparedStarts"].append(record)
        parent["_activeStart"] = record
        return {"parent": parent, "record": record}

    def _chain_start_after(self, value, context):
        parent, record = value["parent"], value["record"]
        self._chain_check(parent)
        if (parent["_activeStart"] is not record or record["_activeRequest"] is not None
                or record["_activePlan"] is not None):
            raise NativeObservationError("chain prepared start has a missing request return")
        self._chain_result(record, context, boolean=False)
        reason = record["returnValue"]
        if reason >= len(MOTION_DECISIONS):
            raise NativeObservationError("chain prepared start reason differs")
        record.update(startReason=reason, startReasonName=MOTION_DECISIONS[reason], accepted=reason == 0)
        requests = record["motionRequests"]
        if record["accepted"] != bool(requests and requests[0]["decision"] == 0):
            raise NativeObservationError("chain prepared start/request results disagree")
        plans = record["hopPlans"]
        if requests:
            expected_reason = requests[0]["decision"]
            if expected_reason in (2, 3, 4, 5):
                # After native preparation, BLOCKED/SIDE_TILE/TERRAIN/OCCUPIED
                # all retry as PROFILE. The nested request keeps its exact
                # decision; none of these grants a new candidate search.
                expected_reason = 8
        elif plans and plans[0]["decision"] != 0:
            expected_reason = plans[0]["decision"]
        elif not plans and reason == 9 and record["engineFlagsAtEntry"] & 2:
            # The actual pre-plan SingleMovement guard returns ALREADY_ACTIVE.
            # Native MapObject_CheckSingleMovement tests flag bit1 only.
            expected_reason = 9
        else:
            expected_reason = 8  # No planner denial: only explicit preparation failure.
        if reason != expected_reason:
            raise NativeObservationError("chain start reason lacks matching native stage")
        del record["_activeRequest"]
        del record["_activePlan"]
        parent["_activeStart"] = None

    def _chain_plan_before(self):
        parent = self.reposition_contexts[-1]
        start = parent["_activeStart"]
        self._chain_caller("ActorSystem_RequestMotion", actor=True)
        self._chain_check(parent)
        pointer = self.session.emu.memory.register_arm9.r0 & 0xFFFFFFFF
        raw = public_bytes(self.session, pointer, 48)
        word = lambda offset: int.from_bytes(raw[offset:offset + 4], "little")
        pair = lambda offset: [int.from_bytes(raw[n:n + 2], "little", signed=True)
                               for n in (offset, offset + 2)]
        if (word(8) != parent["worldContext"]["fieldPointer"]
                or word(16) != start["objectPointer"] or pair(32) != start["target"]
                or raw[47] != start["distance"] or raw[44] not in (1, 2)):
            raise NativeObservationError("chain Hop plan arguments do not match attempt")
        if start["hopPlans"] or start["motionRequests"]:
            raise NativeObservationError("chain Hop plan count/order differs")
        record = {"callPointer": pointer, "inputHex": raw.hex(),
                  "profilePointer": word(0), "lanePointer": word(4),
                  "fieldPointer": word(8), "surfaceCatalogPointer": word(12),
                  "objectPointer": word(16),
                  "startBaseY": self._chain_signed(word(20)),
                  "targetBaseY": self._chain_signed(word(24)),
                  "origin": pair(28), "target": pair(32), "delta": pair(36),
                  "inputTrajectory": word(40), "operation": raw[44],
                  "spotState": raw[45], "direction": raw[46], "distance": raw[47],
                  "laneHex": public_bytes(self.session, word(4), 72).hex()}
        start["hopPlans"].append(record)
        start["_activePlan"] = record
        return {"parent": parent, "start": start, "record": record}

    def _chain_plan_after(self, value, context):
        parent, start, record = value["parent"], value["start"], value["record"]
        self._chain_check(parent)
        if parent["_activeStart"] is not start or start["_activePlan"] is not record:
            raise NativeObservationError("chain Hop plan return lost its parent")
        decision = context["returnValue"]
        if not 0 <= decision < len(MOTION_DECISIONS):
            raise NativeObservationError("chain Hop plan decision enum differs")
        raw = public_bytes(self.session, record["callPointer"], 48)
        before = bytes.fromhex(record["inputHex"])
        if raw[:40] + raw[44:] != before[:40] + before[44:]:
            raise NativeObservationError("chain Hop plan inputs changed before return")
        self._chain_result(record, context, boolean=False)
        record.update(decision=decision, decisionName=MOTION_DECISIONS[decision],
                      outputTrajectory=int.from_bytes(raw[40:44], "little"))
        start["_activePlan"] = None

    def _chain_request_before(self):
        if not self.reposition_contexts:
            return None
        parent = self.reposition_contexts[-1]
        start = parent["_activeStart"]
        if start is None:
            raise NativeObservationError("chain request has no owning prepared start")
        if (start["_activePlan"] is not None or len(start["hopPlans"]) != 1
                or start["hopPlans"][0].get("decision") != 0):
            raise NativeObservationError("chain request has no returned accepted Hop plan")
        self._chain_caller("OverworldWildSpawns_StartPreparedCustomJumpCommandTimed")
        self._chain_check(parent)
        regs = self.session.emu.memory.register_arm9
        state, slot, lane, kind = [getattr(regs, key) & 0xFFFFFFFF for key in ("r0", "r1", "r2", "r3")]
        words = self._chain_words(7)
        if (state != parent["statePointer"] or slot != parent["slot"] or kind != 5
                or any(value > limit for value, limit in zip(words, (255, 255, 255, 65535, 255, 255, 65535)))):
            raise NativeObservationError("chain motion request arguments do not match attempt")
        if start["motionRequests"]:
            raise NativeObservationError("chain motion request count differs")
        record = {"kind": kind, "laneHex": public_bytes(self.session, lane, 72).hex(),
                  **dict(zip(("visibility", "arc", "facing", "duration", "spin", "sway", "surfaceId"), words))}
        start["motionRequests"].append(record)
        start["_activeRequest"] = record
        return {"parent": parent, "start": start, "record": record}

    def _chain_request_after(self, value, context):
        parent, start, record = value["parent"], value["start"], value["record"]
        self._chain_check(parent)
        if parent["_activeStart"] is not start or start["_activeRequest"] is not record:
            raise NativeObservationError("chain request return lost its parent")
        decision = context["returnValue"]
        if not 0 <= decision < len(MOTION_DECISIONS):
            raise NativeObservationError("chain motion decision enum differs")
        self._chain_result(record, context, boolean=False)
        record.update(decision=decision, decisionName=MOTION_DECISIONS[decision])
        start["_activeRequest"] = None

    def _player_step_before(self):
        rt, emu = self.session.rt, self.session.emu
        pointer = emu.memory.register_arm9.r0 & 0xFFFFFFFF
        player = rt.player_ptr(emu)
        if not player or pointer != player:
            return None  # NPC admissions are not player steps.
        if pointer & 3 or not 0x02000000 <= pointer < 0x02400000 - 0x12C:
            raise NativeObservationError("player step uses an invalid current object")
        before = rt.object_state(emu, pointer)
        if not before["flags"] & 1:
            return None  # Object construction is not an active player move.
        direction = emu.memory.register_arm9.r1 & 0xFFFFFFFF
        if direction > 3:
            raise NativeObservationError("player step direction is not cardinal")
        return {"objectPointer": pointer, "direction": direction,
                "mapId": rt.field_map_id(emu), "objectBefore": before}

    def _install_player_collision_identity(self, stock):
        # Include the decisive raw4 -> final2 mapping, not just entry bytes.
        # The second span binds the normal walking BL and its continuation.
        spans = ((PLAYER_WALK_COLLISION, 0x74), (PLAYER_WALK_COLLISION_RETURN - 4, 8))
        identity = []
        for address, size in spans:
            expected = stock[address - 0x02000000:address - 0x02000000 + size]
            if len(expected) != size or not any(
                    base <= address and address + size <= base + len(data)
                    and data[address - base:address - base + size] == expected
                    for base, data in self.session.code_regions):
                raise NativeObservationError("walking collision full body/caller differs from packaged ROM")
            identity.append((address, expected))
        self.player_collision_identity = tuple(identity)

    def _check_player_collision_identity(self):
        for address, expected in self.player_collision_identity:
            if self.session.read(address, len(expected)) != expected:
                raise NativeObservationError("walking collision full body/caller live identity differs")

    def _player_collision_before(self):
        self._check_player_collision_identity()
        rt, emu = self.session.rt, self.session.emu
        registers = emu.memory.register_arm9
        pointer = registers.r1 & 0xFFFFFFFF
        if pointer != rt.player_ptr(emu):
            raise NativeObservationError("walking collision does not own the current player")
        if pointer & 3 or not 0x02000000 <= pointer <= 0x02400000 - 0x12C:
            raise NativeObservationError("walking collision player pointer is invalid")
        direction = registers.r2 & 0xFFFFFFFF
        if direction > 3:
            raise NativeObservationError("walking collision direction is not cardinal")
        context = self._world_context()
        avatar = registers.r0 & 0xFFFFFFFF
        if avatar != rt.unsigned(emu, context["fieldPointer"] + 0x40):
            raise NativeObservationError("walking collision avatar is not current")
        before = rt.object_state(emu, pointer)
        if not before["flags"] & 1:
            raise NativeObservationError("walking collision player is inactive")
        dx, dz = ((0,-1),(0,1),(-1,0),(1,0))[direction]
        return {"objectPointer": pointer, "avatarPointer": avatar, "direction": direction,
                "callerReturn": PLAYER_WALK_COLLISION_RETURN, "context": context,
                "origin": [before["x"], before["y"]],
                "target": [before["x"] + dx, before["y"] + dz], "objectBefore": before}

    def _player_collision_after(self, value, context):
        self._check_player_collision_identity()
        rt, emu = self.session.rt, self.session.emu
        if rt.player_ptr(emu) != value["objectPointer"] or self._world_context() != value["context"]:
            raise NativeObservationError("walking collision changed field or player before return")
        mask = context["returnValue"]
        if type(mask) is not int or mask < 0 or mask & ~0x2F:
            raise NativeObservationError("walking collision returned an unknown reason")
        after = rt.object_state(emu, value["objectPointer"])
        if any(after[k] != value["objectBefore"][k] for k in ("x","y","x_prev","y_prev","pos_x","pos_y","pos_z")):
            raise NativeObservationError("walking collision query changed player position")
        return {**value, "objectAfter": after, "collisionMask": mask,
                "meaning": "stock walking collision query; mask 0x2 is object occupancy, not admission"}

    def _player_step_after(self, value, context):
        rt, emu = self.session.rt, self.session.emu
        pointer = value["objectPointer"]
        if rt.player_ptr(emu) != pointer or rt.field_map_id(emu) != value["mapId"]:
            raise NativeObservationError("player step changed its current field/object before return")
        after, before = rt.object_state(emu, pointer), value["objectBefore"]
        dx, dz = ((0, -1), (0, 1), (-1, 0), (1, 0))[value["direction"]]
        target = [before["x"] + dx, before["y"] + dz]
        if [after["x"], after["y"]] != target \
                or [after["x_prev"], after["y_prev"]] != [before["x"], before["y"]] \
                or [after["pos_x"], after["pos_z"]] != [before["pos_x"], before["pos_z"]]:
            raise NativeObservationError("player admission did not retain origin and reserve exactly one cardinal tile")
        self.player_steps_admitted += 1
        receipt = {**value, "objectAfter": after, "stepIndex": self.player_steps_admitted,
                "origin": [before["x"], before["y"]], "target": target,
                "meaning": "native tile admission; not rendered or terminal completion"}
        control = getattr(self.session, "route_control", None)
        if control is not None:
            control.player_step_admitted(receipt)
        return receipt

    def _world_context(self):
        rt, emu = self.session.rt, self.session.emu
        state = rt.ACTOR_DESCRIPTOR["state"]
        return {"fieldPointer": rt.unsigned(emu, rt.G_FIELD_SYS_PTR),
                "statePointer": rt.WILD_STATE, "mapId": rt.field_map_id(emu),
                **{name: rt.unsigned(emu, state["address"] + state["offsets"][name], 2)
                   for name in ("fieldEpoch", "mapGeneration")}}

    @staticmethod
    def _prepared_fields(data):
        encounter = {"personality": int.from_bytes(data[12:16], "little"),
                     "species": int.from_bytes(data[16:18], "little"),
                     "form": data[18], "level": data[19]}
        value = {"position": [int.from_bytes(data[n:n + 4], "little", signed=True) for n in (0, 4)],
                 "preparedEncounter": encounter}
        if len(data) >= 30:
            value["startup"] = {
                "target": [int.from_bytes(data[n:n + 2], "little", signed=True) for n in (20, 22)],
                "origin": [int.from_bytes(data[n:n + 2], "little", signed=True) for n in (24, 26)],
                "locomotion": data[28], "hopDirection": data[29]}
        if len(data) >= 36:
            value["startup"]["targetBaseY"] = int.from_bytes(
                data[32:36], "little", signed=True)
            value["startupHex"] = data[20:36].hex()
        return value

    def _prepared_call(self):
        regs = self.session.emu.memory.register_arm9
        slot = regs.r3 & 0xFFFFFFFF
        if slot >= 7:
            return None
        # Both authenticated linked functions have this exact five-argument
        # AAPCS signature. include/overworld_wild_helper.h owns the value layout:
        # position(12), encounter(8), then startup(10). No private actor offsets.
        return {"slot": slot, "terrain": regs.r2 & 0xFFFFFFFF,
                "statePointer": regs.r0 & 0xFFFFFFFF, "fieldPointer": regs.r1 & 0xFFFFFFFF,
                "preparedPointer": int.from_bytes(public_bytes(self.session, regs.sp, 4), "little"),
                "worldContext": self._world_context()}

    def _refill_cost_before(self):
        regs = self.session.emu.memory.register_arm9
        return {"arguments": [getattr(regs, "r" + str(i)) & 0xFFFFFFFF for i in range(4)],
                "worldContext": self._world_context()}

    def _archive_cost_before(self):
        regs = self.session.emu.memory.register_arm9
        return {"arguments": [getattr(regs, "r" + str(i)) & 0xFFFFFFFF for i in range(4)],
                "caller": regs.lr & 0xFFFFFFFE}

    def _archive_cost_after(self, value, context):
        return {**value, "scope": "read-only inclusive archive call; raw API arguments",
                "acceptedProof": False}

    def _refill_cost_after(self, value, context):
        if self._world_context() != value["worldContext"]:
            raise NativeObservationError("refill cost call changed world context")
        return {**value, "scope": "read-only inclusive spawn call cost", "acceptedProof": False}

    def _spawn_cost_before(self):
        parent = (self.finalization_contexts or self.spawn_contexts)[-1]
        regs = self.session.emu.memory.register_arm9
        return {"parent": parent, "arguments": [getattr(regs, "r" + str(i)) & 0xFFFFFFFF
                                                 for i in range(4)]}

    def _spawn_cost_after(self, value, context):
        parent = value["parent"]
        if not any(item is parent for item in self.finalization_contexts + self.spawn_contexts) \
                or self._world_context() != parent["worldContext"]:
            raise NativeObservationError("spawn timing child lost its parent or world")
        return {"scope": "call-timing-only; raw first four argument registers",
                "slot": parent["slot"], "finalizationId": parent.get("finalizationId"),
                "arguments": value["arguments"]}

    def _destination_before(self):
        if not self.finalization_contexts:
            raise NativeObservationError("spawn destination search has no finalizer owner")
        parent = self.finalization_contexts[-1]
        regs = self.session.emu.memory.register_arm9
        if (regs.r0 & 0xFFFFFFFF, regs.r1 & 0xFFFFFFFF) != (
                parent["statePointer"], parent["fieldPointer"]):
            raise NativeObservationError("spawn destination search differs from its finalizer owner")
        pointer = regs.r3 & 0xFFFFFFFF
        value = {"spawnAttemptId": parent.get("spawnAttemptId"),
                "finalizationId": parent["finalizationId"], "slot": parent["slot"],
                "destinationMask": regs.r2 & 0xFFFF, "positionPointer": pointer,
                "worldContext": deepcopy(parent["worldContext"]),
                "inputPositionHex": public_bytes(self.session, pointer, 8).hex(),
                "candidateQueryCount": 0}
        self.destination_contexts.append(value)
        return value

    def _destination_after(self, value, context):
        if not self.destination_contexts or self.destination_contexts[-1] is not value \
                or not self.finalization_contexts \
                or self.finalization_contexts[-1]["finalizationId"] != value["finalizationId"] \
                or self._world_context() != value["worldContext"] \
                or context["returnValue"] not in (0, 1):
            raise NativeObservationError("spawn destination search lost its finalizer owner or world")
        self.destination_contexts.pop()
        result = {**value, "outputPositionHex": public_bytes(
            self.session, value["positionPointer"], 8).hex()}
        if value["spawnAttemptId"] is not None and self.spawn_queue_contexts:
            self.latest_destination_results[value["spawnAttemptId"]] = deepcopy(result)
        return result

    def _allowed_tile_before(self):
        if not self.destination_contexts:
            return {"owner": "chain", "value": self._landing_detail_before("terrain")}
        parent = self.destination_contexts[-1]
        regs = self.session.emu.memory.register_arm9
        expected_mask = parent["destinationMask"] & DESTINATION_NATIVE_TILE_MASK
        if (regs.r0 & 0xFFFFFFFF) != parent["worldContext"]["fieldPointer"] \
                or (regs.r1 & 0xFFFF) != expected_mask:
            raise NativeObservationError("spawn destination query differs from its scanner owner")
        parent["candidateQueryCount"] += 1
        if parent["candidateQueryCount"] > 255:
            raise NativeObservationError("spawn destination query count exceeded its bounded call")
        return {"owner": "destination", "value": parent}

    def _allowed_tile_after(self, value, context):
        if value["owner"] == "chain":
            return self._landing_detail_after(value["value"], context)
        if not self.destination_contexts or self.destination_contexts[-1] is not value["value"] \
                or context["returnValue"] not in (0, 1):
            raise NativeObservationError("spawn destination query lost its scanner owner")
        return None

    def _spawn_queue_before(self):
        regs = self.session.emu.memory.register_arm9
        slot = regs.r3 & 0xFFFFFFFF
        if slot >= 7:
            return None
        self.spawn_queue_id += 1
        value = {"statePointer": regs.r0 & 0xFFFFFFFF,
                "fieldPointer": regs.r1 & 0xFFFFFFFF,
                "terrain": regs.r2 & 0xFFFFFFFF, "slot": slot,
                "worldContext": self._world_context(),
                "previousFinalizationId": self.finalization_id,
                "spawnAttemptId": self.spawn_queue_id}
        self.spawn_queue_contexts.append(value)
        return value

    def _spawn_queue_after(self, value, context):
        if not self.spawn_queue_contexts or self.spawn_queue_contexts[-1] is not value:
            raise NativeObservationError("SpawnOne return lost its attempt owner")
        self.spawn_queue_contexts.pop()
        if context["returnValue"] != 1:
            self.latest_destination_results.pop(value["spawnAttemptId"], None)
            return {**value, "queued": False}
        prior = self.finalizations.get(value["slot"])
        if prior is not None and prior["finalizationId"] > value["previousFinalizationId"] \
                and all(prior[key] == value[key] for key in (
                    "statePointer", "fieldPointer", "terrain", "slot", "worldContext")) \
                and self._world_context() == value["worldContext"]:
            # Only an authenticated successful enqueue can cross one completed
            # queue. The next boundary expires it even when creation is cancelled.
            self.queued_finalizations[value["slot"]] = prior["finalizationId"]
            self.pending_destination_scans.pop(value["slot"], None)
            self.latest_destination_results.pop(value["spawnAttemptId"], None)
            return {**value, "queued": True, "pendingDestination": False,
                    "finalizationId": prior["finalizationId"]}
        final = self.latest_finalization_results.get(value["slot"])
        destination = self.latest_destination_results.get(value["spawnAttemptId"])
        if final is None or destination is None \
                or final.get("finalizationId", 0) <= value["previousFinalizationId"] \
                or final.get("returnValue") != 0 \
                or destination.get("finalizationId") != final.get("finalizationId") \
                or destination.get("candidateQueryCount") != 0 \
                or destination.get("spawnAttemptId") != value["spawnAttemptId"] \
                or any(final.get(key) != value[key] for key in (
                    "statePointer", "fieldPointer", "terrain", "slot", "worldContext")) \
                or self._world_context() != value["worldContext"]:
            raise NativeObservationError(
                "queued spawn lacks its exact finalizer or pending destination scan")
        pending = {key: deepcopy(final[key]) for key in (
            "statePointer", "fieldPointer", "terrain", "slot", "preparedPointer", "worldContext")}
        pending.update(spawnAttemptId=value["spawnAttemptId"])
        self.pending_destination_scans[value["slot"]] = pending
        self.latest_destination_results.pop(value["spawnAttemptId"], None)
        return {**value, "queued": True, "pendingDestination": True,
                "finalizationId": final["finalizationId"]}

    def _finalize_before(self):
        value = self._prepared_call()
        if value is None:
            return None
        self.finalization_id += 1
        value["finalizationId"] = self.finalization_id
        if self.spawn_queue_contexts:
            value["spawnAttemptId"] = self.spawn_queue_contexts[-1]["spawnAttemptId"]
        else:
            pending = self.pending_destination_scans.get(value["slot"])
            if pending is not None:
                if any(value.get(key) != pending[key] for key in (
                        "statePointer", "fieldPointer", "terrain", "slot", "preparedPointer", "worldContext")):
                    self.pending_destination_scans.pop(value["slot"], None)
                else:
                    value["spawnAttemptId"] = pending["spawnAttemptId"]
        self.latest_finalizations[value["slot"]] = self.finalization_id
        for slot, old in list(self.finalizations.items()):
            if slot == value["slot"] or old["preparedPointer"] == value["preparedPointer"]:
                del self.finalizations[slot]
        for old in self.finalization_contexts:
            if old["preparedPointer"] == value["preparedPointer"]:
                old["superseded"] = True
        data = public_bytes(self.session, value["preparedPointer"], 20)
        fields = self._prepared_fields(data)
        value.update(inputPrefixHex=data.hex(), inputPosition=fields["position"],
                     inputEncounter=fields["preparedEncounter"], resolverReceipts=[])
        self.finalization_contexts.append(value)
        return value

    def _finalize_after(self, value, context):
        self.finalization_contexts.remove(value)
        current = self._world_context()
        result = {key: deepcopy(data) for key, data in value.items() if key != "superseded"}
        result.update(returnWorldContext=current, returnValue=context["returnValue"], pairEligible=False)
        if context["returnValue"] == 1:
            data = public_bytes(self.session, value["preparedPointer"], 36)
            result.update(preparedPrefixHex=data[:30].hex(), **self._prepared_fields(data))
            result["pairEligible"] = (
                current == value["worldContext"]
                and all(value[key] == current[key] for key in ("statePointer", "fieldPointer"))
                and current["fieldPointer"] != 0
                and self.latest_finalizations.get(value["slot"]) == value["finalizationId"]
                and not value.get("superseded")
                and context["setupMode"] == ("prepared" if self.session.prepared else "normal"))
        self.latest_finalization_results[value["slot"]] = deepcopy(result)
        if context["returnValue"] == 1:
            self.pending_destination_scans.pop(value["slot"], None)
        return result

    def _spawn_before(self):
        value = self._prepared_call()
        if value is None:
            return None
        data = public_bytes(self.session, value["preparedPointer"], 36)
        prior = self.finalizations.pop(value["slot"], None)
        # A mismatching consumer still uses up that receipt; pointer reuse in
        # another slot cannot leave an old value available for a later spawn.
        for slot, old in list(self.finalizations.items()):
            if old["preparedPointer"] == value["preparedPointer"] \
                    or old["worldContext"] != value["worldContext"]:
                del self.finalizations[slot]
        pair = {"status": "missing"}
        if prior is not None:
            pair = {"status": "matched", "receipt": prior}
            if any(prior[key] != value[key] for key in (
                    "statePointer", "fieldPointer", "slot", "terrain", "preparedPointer", "worldContext")) \
                    or prior["setupMode"] != ("prepared" if self.session.prepared else "normal"):
                pair["status"] = "context-mismatch"
            elif prior["preparedPrefixHex"] != data[:30].hex():
                pair["status"] = "prefix-mismatch"
        value.update(preparedPrefixHex=data[:30].hex(), **self._prepared_fields(data),
                     initialLandingHeight={"status": "not-observed", "surfaceLegality": "unknown"},
                     jumpReceipts=[], resolverReceipts=[], finalization=pair)
        self.spawn_contexts.append(value)
        return value

    def _spawn_after(self, value, context):
        self.spawn_contexts.remove(value)
        if value["finalization"]["status"] == "matched" and self._world_context() != value["worldContext"]:
            value["finalization"]["status"] = "context-mismatch"
        subject = self._subject(value["slot"])
        if context["returnValue"] == 1 and (subject.get("status") != "observed-public-subject"
                or subject.get("handle", {}).get("slot") != value["slot"]
                or any(subject.get("subjectIdentity" if key == "personality" else key) != expected
                       for key, expected in value["preparedEncounter"].items())):
            raise NativeObservationError("successful spawn does not match its prepared encounter and slot")
        trace = self.spawn_height_trace
        if (context["returnValue"] == 1 and trace is not None
                and trace["subject"] is None and trace["slot"] == value["slot"]
                and trace["worldContext"] == value["worldContext"]):
            trace["subject"] = deepcopy(subject)
        return {**value, "publicSubject": subject}

    def _jump_before(self):
        rt, emu = self.session.rt, self.session.emu
        regs = emu.memory.register_arm9
        slot = regs.r2 & 0xFFFFFFFF
        if not self.spawn_contexts or self.spawn_contexts[-1]["slot"] != slot:
            return None
        source = rt.wild_spawn(emu, slot)
        if regs.r3 & 0xFFFFFFFF != source["object"]:
            raise NativeObservationError("spawn motion does not use its current native object")
        origin = rt.object_state(emu, source["object"])
        target = public_bytes(self.session, (regs.sp & 0xFFFFFFFF) + 8, 8)
        player_pointer = rt.player_ptr(emu)
        if player_pointer & 3 or not 0x02000000 <= player_pointer < player_pointer + 0x12C <= 0x02400000:
            raise NativeObservationError("spawn motion has no valid current player object")
        player = rt.object_state(emu, player_pointer)
        value = {"slot": slot, "sourceIdentity": source, "origin": [origin["x"], origin["y"]],
                "target": [int.from_bytes(target[n:n + 4], "little", signed=True) for n in (0, 4)],
                # Entry data is never relabelled as the later coherent pose.
                "playerAtEntry": {"pointer": player_pointer, "mapId": rt.field_map_id(emu),
                                  "tile": [player["x"], player["y"]]},
                "landingHeight": {"status": "not-observed", "surfaceLegality": "unknown"}}
        if self.spawn_contexts[-1].get("_activeSpawnJump") is not None:
            raise NativeObservationError("spawn jump reentered its encounter")
        self.spawn_contexts[-1]["_activeSpawnJump"] = value
        return value

    def _jump_after(self, value, context):
        if self.spawn_height_contexts:
            raise NativeObservationError("spawn jump has a missing landing-height return")
        if self.spawn_contexts[-1].pop("_activeSpawnJump", None) is not value:
            raise NativeObservationError("spawn jump lost its encounter")
        receipt = {**value, "publicSubject": self._subject(value["slot"]),
                   "returnValue": context["returnValue"]}
        self.spawn_contexts[-1]["jumpReceipts"].append(deepcopy(receipt))
        return receipt

    def _spawn_height_check(self, record):
        rt, emu = self.session.rt, self.session.emu
        if (not self.spawn_contexts or self.spawn_contexts[-1] is not record["_spawn"]
                or self._world_context() != record["worldContext"]
                or rt.wild_spawn(emu, record["slot"]) != record["sourceIdentity"]):
            raise NativeObservationError("spawn landing source or world changed")

    def _spawn_height_terrain(self, record):
        terrain = self.session.rt.loaded_terrain_cell(self.session.emu, *record["target"])
        if terrain is not None and ([terrain.get("x"), terrain.get("y")] != record["target"]
                or terrain.get("provenance", {}).get("fieldPointer") != record["worldContext"]["fieldPointer"]):
            raise NativeObservationError("spawn landing loaded terrain belongs to another point/world")
        return {"status": "observed" if terrain is not None else "unknown", "cell": terrain}

    def _spawn_height_before(self):
        parent = self.spawn_contexts[-1]
        jump = parent.get("_activeSpawnJump")
        initial = jump is None
        locomotion = parent["startup"]["locomotion"]
        if initial and locomotion != 7:
            return None
        if not initial and locomotion != 4:
            return None
        self._chain_caller(
            "OverworldWildSpawns_SpawnPreparedEncounter" if initial
            else "OverworldWildSpawns_StartPreparedCustomJumpCommandTimed",
            cache=self.spawn_height_call_sites)
        regs = self.session.emu.memory.register_arm9
        args = [getattr(regs, key) & 0xFFFFFFFF for key in ("r0", "r1", "r2", "r3")]
        rt, emu = self.session.rt, self.session.emu
        source = rt.wild_spawn(emu, parent["slot"]) if initial else jump["sourceIdentity"]
        if args[:2] != [parent["fieldPointer"], source["object"]]:
            raise NativeObservationError("spawn landing height field/object differs")
        point = list(map(self._chain_signed, args[2:]))
        target = parent["position"] if initial else jump["target"]
        if point != target:
            return None  # Intermediate height seeding is not the landing target.
        if point != parent["position"] or point != parent["startup"]["target"]:
            raise NativeObservationError("spawn landing borrows a different encounter target")
        owner = parent["initialLandingHeight"] if initial else jump["landingHeight"]
        if self.spawn_height_contexts or owner["status"] != "not-observed":
            raise NativeObservationError("duplicate or reentered spawn landing height")
        if (any(source.get(key) != value for key, value in parent["preparedEncounter"].items())
                or source.get("map_id") != parent["worldContext"]["mapId"]
                or not source.get("active") or not source.get("encounter_generation")):
            raise NativeObservationError("spawn landing does not name its prepared encounter")
        engine = rt.live_wild_object_identity(emu, parent["slot"])
        if (engine.get("pointer") != args[1] or not engine.get("in_manager") or not engine.get("active")
                or engine.get("object_manager") != engine.get("current_manager")
                or engine.get("object_map_id") != parent["worldContext"]["mapId"]
                or engine.get("object_id") != source.get("object_id")
                or engine.get("script_id") != 2074
                or engine.get("id_lookup", {}).get("status") != "complete"
                or engine.get("id_lookup", {}).get("eligible_count") != 1
                or engine.get("id_lookup", {}).get("pointer_matches") is not True):
            raise NativeObservationError("spawn landing native object binding differs")
        record = {"status": "observed", "observationVersion": 1, "slot": parent["slot"],
                  "sourceIdentity": deepcopy(source), "engineIdentity": engine,
                  "worldContext": deepcopy(parent["worldContext"]), "target": point,
                  "preparedPointer": parent["preparedPointer"],
                  "preparedEncounter": deepcopy(parent["preparedEncounter"]),
                  "positionBefore": rt.object_state(emu, args[1]),
                  "surfaceQuery": None, "heightRefresh": None, "_activeDetail": None, "_spawn": parent,
                  "initialPlacement": initial,
                  "surfaceLegality": "unknown", "acceptedProof": False,
                  "scope": "native own-target height preparation; not settled pose or surface legality"}
        self._spawn_height_check(record)
        record["loadedTerrainBefore"] = self._spawn_height_terrain(record)
        self.spawn_height_contexts.append(record)
        return record

    def _spawn_surface_before(self):
        record = self.spawn_height_contexts[-1]
        self._spawn_height_check(record)
        self._chain_caller("OverworldWildSpawns_ApplySurfaceHeight", cache=self.spawn_height_call_sites)
        regs = self.session.emu.memory.register_arm9
        point = [self._chain_signed(regs.r1 & 0xFFFFFFFF), self._chain_signed(regs.r2 & 0xFFFFFFFF)]
        if (regs.r0 & 0xFFFFFFFF != record["worldContext"]["fieldPointer"] or point != record["target"]
                or record["heightRefresh"] is None
                or "returnValue" not in record["heightRefresh"]
                or record["surfaceQuery"] is not None or record["_activeDetail"] is not None):
            raise NativeObservationError("spawn landing surface point/order differs")
        detail = {"kind": "surface", "point": point, "outputPointer": regs.r3 & 0xFFFFFFFF}
        record["surfaceQuery"] = record["_activeDetail"] = detail
        return {"record": record, "detail": detail}

    def _spawn_refresh_before(self):
        record = self.spawn_height_contexts[-1]
        self._spawn_height_check(record)
        self._chain_caller("OverworldWildSpawns_ResolveObjectLandingHeight",
                           cache=self.spawn_height_call_sites,
                           target=SPAWN_REFRESH_HEIGHT)
        if (record["_activeDetail"] is not None or record["surfaceQuery"] is not None
                or record["heightRefresh"] is not None
                or self.session.emu.memory.register_arm9.r0 & 0xFFFFFFFF != record["sourceIdentity"]["object"]):
            raise NativeObservationError("spawn height refresh source/order differs")
        detail = {"kind": "height-refresh", "objectPointer": record["sourceIdentity"]["object"],
                  "positionBefore": self.session.rt.object_state(self.session.emu, record["sourceIdentity"]["object"])}
        record["heightRefresh"] = record["_activeDetail"] = detail
        return {"record": record, "detail": detail}

    def _spawn_height_detail_after(self, value, context):
        record, detail = value["record"], value["detail"]
        self._spawn_height_check(record)
        if record["_activeDetail"] is not detail:
            raise NativeObservationError("spawn height detail lost its return")
        self._chain_result(detail, context)
        if detail["kind"] == "surface":
            detail["hit"] = None
            if detail["returnValue"]:
                raw = public_bytes(self.session, detail["outputPointer"], 8)
                detail["hit"] = {"height": int.from_bytes(raw[:4], "little", signed=True),
                    "surfaceId": int.from_bytes(raw[4:6], "little"), "surfaceType": raw[6],
                    "nodeId": raw[7], "rawHex": raw.hex()}
        else:
            detail["positionAfter"] = self.session.rt.object_state(self.session.emu, record["sourceIdentity"]["object"])
        record["_activeDetail"] = None

    def _spawn_height_after(self, record, context):
        control = getattr(self.session, "spawn_height_control", None)
        reader = lambda: self._read_spawn_height_after(record, context)
        if control is None:
            result = reader()
        else:
            before = control.state
            try:
                result = control.capture(self.session, record, reader)
            except Exception as error:
                if getattr(error, "fatal", False):
                    self.session.abort_native_control(error)
                raise
            if before == "armed" and control.state == "complete":
                value = control.result()
                self._queue("spawn-height-read-control", context,
                            {**{k: v for k, v in value.items() if k != "receipt"}, **value["receipt"]})
                self.spawn_height_trace = {
                    # The initial height read is nested inside spawn creation.
                    # Bind the public actor at the successful outer return.
                    "subject": None,
                    "slot": record["slot"],
                    "worldContext": deepcopy(record["worldContext"]),
                    "started": False,
                    "waiting": 0,
                    "samples": 0,
                    "complete": False,
                }
        self.spawn_height_contexts.remove(record)
        return result

    def _read_spawn_height_after(self, record, context):
        self._spawn_height_check(record)
        query, refresh = record["surfaceQuery"], record["heightRefresh"]
        if refresh is None or "returnValue" not in refresh:
            raise NativeObservationError("spawn landing has a missing native height refresh")
        if (record["_activeDetail"] is not None or query is None
                or "returnValue" not in query):
            raise NativeObservationError("spawn landing has a missing surface return")
        elevated = query["returnValue"] == 1 and query["hit"]["surfaceId"] != 0xFFFF
        canopy = elevated and query["hit"]["surfaceType"] == 4
        rt, emu = self.session.rt, self.session.emu
        engine_after = rt.live_wild_object_identity(emu, record["slot"])
        if (any(engine_after.get(key) != record["engineIdentity"].get(key) for key in
                ("pointer", "in_manager", "active", "current_manager", "object_manager", "manager_index",
                 "object_id", "object_map_id", "script_id"))
                or engine_after.get("id_lookup", {}).get("status") != "complete"
                or engine_after.get("id_lookup", {}).get("eligible_count") != 1
                or engine_after.get("id_lookup", {}).get("pointer_matches") is not True):
            raise NativeObservationError("spawn landing native object changed before return")
        after = rt.object_state(emu, record["sourceIdentity"]["object"])
        if [after["x"], after["y"]] != record["target"]:
            raise NativeObservationError("spawn landing height returned at a different tile")
        terrain = self._spawn_height_terrain(record)
        if (record["loadedTerrainBefore"]["status"] == terrain["status"] == "observed"
                and record["loadedTerrainBefore"] != terrain):
            raise NativeObservationError("spawn landing loaded terrain changed during height preparation")
        self._spawn_height_check(record)
        if elevated and not canopy:
            height_source = "catalog-surface"
        elif refresh["returnValue"] and canopy:
            height_source = "native-plus-catalog-offset"
        elif refresh["returnValue"]:
            height_source = "native-refresh"
        else:
            height_source = "unknown"
        return {**{key: deepcopy(value) for key, value in record.items() if not key.startswith("_")},
                "returnValue": None, "nativeReturnKind": "void", "positionAfter": after,
                "engineIdentityAfter": engine_after,
                "loadedTerrain": terrain,
                "heightSource": height_source}

    def _resolver_before(self):
        regs = self.session.emu.memory.register_arm9
        request = public_bytes(self.session, regs.r2, 44)
        return {"requestHex": request.hex(), "resultAddress": regs.r3 & 0xFFFFFFFF,
                "blobAddress": regs.r0 & 0xFFFFFFFF, "blobSize": regs.r1 & 0xFFFFFFFF,
                "fieldPointer": self.session.rt.unsigned(self.session.emu, self.session.rt.G_FIELD_SYS_PTR),
                "heapGeneration": getattr(self.session, "native_heap_generation", None),
                "controlledCall": bool(getattr(self.session, "native_bridge_active", False)),
                # Pin call ownership now; another spawn can be nested later.
                # This private context is never included in the raw receipt.
                "spawnContext": self.spawn_contexts[-1] if self.spawn_contexts else None,
                "finalizationContext": self.finalization_contexts[-1] if self.finalization_contexts else None}

    def _resolver_after(self, value, context):
        if context["returnValue"] != 0:
            return {"requestHex": value["requestHex"], "resolved": False}
        result = public_bytes(self.session, value["resultAddress"], 200)
        if not value["controlledCall"]:
            # Discovery is one bounded private receipt. A later prepared probe
            # must authenticate current code/blob and recheck this field owner.
            # Its own controlled calls cannot replace the natural discovery.
            self.resolver_discovery = {key: value[key] for key in (
                "blobAddress", "blobSize", "fieldPointer", "heapGeneration", "requestHex")}
            self.resolver_discovery.update(status=0,
                entryNativeCycle=context["entry"]["nativeCycle"],
                returnNativeCycle=context["returned"]["nativeCycle"])
        fingerprint = int.from_bytes(result[176:180], "little")
        receipt = {"requestHex": value["requestHex"], "resultHex": result.hex(), "resolved": True,
                   "fingerprint": fingerprint, "sourceSha256": self.source_hash,
                   "lanes": [result[n:n + 72].hex() for n in (0, 72)],
                   "appliedOverrides": int.from_bytes(result[172:176], "little")}
        if fingerprint not in self.profiles and len(self.profiles) >= self.MAX_PROFILES:
            self.profiles.popitem(last=False)
            self.profiles_evicted += 1
        self.profiles[fingerprint] = deepcopy(receipt)
        self.profiles.move_to_end(fingerprint)
        finalization = value["finalizationContext"]
        if finalization is not None and any(active is finalization for active in self.finalization_contexts):
            if len(finalization["resolverReceipts"]) >= self.MAX_SPAWN_RESOLVERS:
                raise NativeObservationError("finalization resolver observation limit reached")
            finalization["resolverReceipts"].append(deepcopy({
                "finalizationId": finalization["finalizationId"],
                "inputEncounter": finalization["inputEncounter"], **receipt}))
        spawn = value["spawnContext"]
        if spawn is not None and any(active is spawn for active in self.spawn_contexts):
            if len(spawn["resolverReceipts"]) >= self.MAX_SPAWN_RESOLVERS:
                raise NativeObservationError("spawn resolver observation limit reached")
            source = self.session.rt.wild_spawn(self.session.emu, spawn["slot"])
            spawn["resolverReceipts"].append(deepcopy({
                "slot": spawn["slot"], "sourceIdentity": source, **receipt}))
        return receipt

    def _commit_policy_address(self, slot):
        # The descriptor publishes the policy member inside each actor slot.
        try:
            descriptor = self.session.rt.ACTOR_DESCRIPTOR
            state = descriptor["state"]
            address, size, stride = state["address"], state["size"], state["actorStride"]
            offset, policy_offset = state["offsets"]["actors"], state["actorPolicyOffset"]
            capacity = descriptor["capacities"]["actors"]
            policy_size = descriptor["structures"]["actorPolicyState"]
            if (any(type(v) is not int for v in
                    (address, size, stride, offset, policy_offset, policy_size, capacity, slot))
                    or not 1 <= capacity <= 32 or not 0 <= slot < capacity
                    or stride < 88 or stride & 3 or offset < 8 or offset & 3
                    or policy_size != 32 or policy_offset < 88
                    or policy_offset + policy_size > stride
                    or address & 3 or not 0x02000000 <= address < address + size <= 0x02400000
                    or offset + stride * capacity > size):
                raise ValueError("invalid span")
            return address + offset + slot * stride + policy_offset
        except (KeyError, TypeError, ValueError) as error:
            raise NativeObservationError("public Walk COMMIT policy layout differs") from error

    def _commit_policy(self, slot):
        raw = public_bytes(self.session, self._commit_policy_address(slot), 32)
        names = ("direction", "counter", "speed", "base", "spotState", "skid", "turn", "resume",
                 "chain", "ticks", "action", "variance", "buffered", "stop", "pending", "pendingSkid", "streamState")
        return raw.hex(), dict(zip(names, (raw[index] for index in (*range(8), *range(16, 25)))))

    def _policy_before(self):
        regs = self.session.emu.memory.register_arm9
        address = regs.r0 & 0xFFFFFFFF
        call = public_bytes(self.session, address, 28)
        if call[:4] != b"\x01\x00\x1c\x00":
            raise NativeObservationError("public Walk policy ABI differs")
        # Public OverworldActorWalkPolicyOperation: retain the chain handoff
        # commands 9..13 on this same authenticated hook. They have no lane or
        # RNG input; INSPECT/binding/variance/effects remain outside this scope.
        if call[9] > 4 and not 9 <= call[9] <= 13:
            return None
        value = {"address": address, "slot": call[8], "operation": call[9], "requestHex": call.hex(),
                 "publicSubject": self._subject(call[8]), "rngReturns": []}
        if call[9] in (1, 4):
            value["laneHex"] = public_bytes(self.session, int.from_bytes(call[4:8], "little"), 72).hex()
            self.policy_contexts.append(value)
        if call[9] == 3:
            subject = value["publicSubject"]
            if (subject.get("status") != "observed-public-subject"
                    or subject.get("handle", {}).get("slot") != call[8]
                    or any(type(subject.get(key)) is not int or subject[key] <= 0
                           for key in ("authorityGeneration", "engineAnchorGeneration", "presentationGeneration"))
                    or any(type(subject.get("handle", {}).get(key)) is not int
                           for key in ("generation", "fieldEpoch", "mapGeneration", "encounterGeneration"))):
                raise NativeObservationError("public Walk COMMIT subject is absent or differs")
            value["laneHex"] = public_bytes(self.session, int.from_bytes(call[4:8], "little"), 72).hex()
            control = getattr(self.session, "walk_policy_control", None)
            read = lambda: self._commit_policy(call[8])
            value["policyBeforeHex"], value["policyBefore"] = (
                control.capture(self, call[8], read) if control is not None else read())
        return value

    def _policy_after(self, value, context):
        if value in self.policy_contexts:
            self.policy_contexts.remove(value)
        response = public_bytes(self.session, value["address"], 28)
        if response[:4] != b"\x01\x00\x1c\x00" or response[8:10] != bytes((value["slot"], value["operation"])):
            raise NativeObservationError("public Walk policy response identity differs")
        after = self._subject(value["slot"])
        if value["operation"] == 3:
            identity = ("status", "handle", "species", "form", "level", "subjectIdentity", "role",
                        "authorityGeneration", "engineAnchorGeneration", "presentationGeneration")
            if any(value["publicSubject"].get(key) != after.get(key) for key in identity):
                raise NativeObservationError("public Walk COMMIT subject identity differs")
            request = bytes.fromhex(value["requestHex"])
            if (response[4:8] != request[4:8] or public_bytes(self.session,
                    int.from_bytes(request[4:8], "little"), 72).hex() != value["laneHex"]):
                raise NativeObservationError("public Walk COMMIT lane differs")
            value["policyAfterHex"], value["policyAfter"] = self._commit_policy(value["slot"])
        if 9 <= value["operation"] <= 13:
            before = value["publicSubject"]
            identity = ("status", "handle", "species", "form", "level", "subjectIdentity", "role",
                        "authorityGeneration", "engineAnchorGeneration", "presentationGeneration")
            if any(before.get(key) != after.get(key) for key in identity) or any(
                    subject.get("status") == "observed-public-subject"
                    and subject["handle"].get("slot") != value["slot"] for subject in (before, after)):
                raise NativeObservationError("public Walk chain response subject identity differs")
        return {**{key: data for key, data in value.items() if key != "address"},
                "responseHex": response.hex(), "publicSubjectAfter": after}

    def _rng_after(self, value, context):
        if len(value["rngReturns"]) >= self.MAX_RNG_DRAWS:
            raise NativeObservationError("public policy RNG observation limit reached")
        value["rngReturns"].append({"value": context["returnValue"], **context["returned"]})
        return None  # The owning policy receipt retains the exact draw order.

    def _friendship_scope(self):
        probe = getattr(self, "wait_probe", None)
        active = getattr(probe, "active", None)
        mode = getattr(getattr(self.session, "spawn_cost_probe", None), "mode", None)
        return (mode == "baseline" and isinstance(active, dict)
                and FRIENDSHIP_WAIT_WINDOW[0] <= active.get("afterQueueFrame", -1)
                <= FRIENDSHIP_WAIT_WINDOW[1])

    def _friendship_before(self):
        registers = self.session.emu.memory.register_arm9
        return {"monPointer": registers.r0 & 0xFFFFFFFF,
                "kind": registers.r1 & 0xFFFFFFFF,
                "location": registers.r2 & 0xFFFFFFFF,
                "callerReturn": registers.lr & 0xFFFFFFFF}

    @staticmethod
    def _friendship_after(value, context):
        return {**value,
                "scope": "late unmounted route wait window; raw native call arguments",
                "timing": "guestTiming is the inclusive ARM9 scheduler interval"}

    def _flush_pending(self, frame):
        while self.pending:
            if len(self.ready) >= self.MAX_EVENTS:
                self.ready.popleft()
                self.events_dropped += 1
            self.ready.append({"frame": frame, "kind": "native-observation",
                               "data": self.pending.popleft()})

    def completed_snapshot(self, snapshot):
        """Retain the one controlled natural Appear Hop across boot frames."""
        trace = self.spawn_height_trace
        if trace is None or trace["complete"]:
            return
        subject = trace["subject"]
        if subject is None or subject.get("status") != "observed-public-subject":
            raise NativeObservationError("spawn height trace has no successful public actor binding")
        actors = [actor for actor in snapshot.get("actors", [])
                  if actor.get("handle") == subject.get("handle")]
        if len(actors) != 1:
            raise NativeObservationError("spawn height trace subject is missing or duplicated")
        actor = actors[0]
        world = trace["worldContext"]
        if (snapshot.get("observationBoundary") != "main-task-queue-completion"
                or snapshot.get("prepared") is not False
                or any(snapshot.get("context", {}).get(key) != world.get(key)
                       for key in ("mapId", "fieldEpoch", "mapGeneration"))):
            raise NativeObservationError("spawn height trace world changed")
        engine = actor.get("engineObject", {})
        command, state = engine.get("movement_cmd"), actor.get("controllerState")
        if type(command) is not int or type(state) is not int \
                or type(engine.get("face_y")) is not int:
            raise NativeObservationError("spawn height trace pose is incomplete")
        clock = {"actorFrame": snapshot.get("actorFrame"),
                 "nativeCycle": snapshot.get("nativeCycle")}
        if any(type(value) is not int or value < 0 for value in clock.values()):
            raise NativeObservationError("spawn height trace clock is incomplete")
        if not trace["started"]:
            if command not in (48, 49, 50, 51):
                trace["waiting"] += 1
                if trace["waiting"] > 120:
                    raise NativeObservationError("spawn height trace did not start within its frame bound")
                return
            trace["started"] = True
        context = {"entry": clock, "returned": clock,
                   "setupMode": "normal", "returnValue": 0}
        self._queue("spawn-appear-hop-frame", context, {
            "subject": deepcopy(subject), "worldContext": deepcopy(world),
            "actor": deepcopy(actor), "actorFrame": clock["actorFrame"],
            "nativeCycle": clock["nativeCycle"],
            "observationBoundary": "main-task-queue-completion",
            "prepared": False,
        })
        trace["samples"] += 1
        if trace["samples"] > 60:
            raise NativeObservationError("spawn height trace exceeded its frame bound")
        if command == 255 and state == 0:
            trace["complete"] = True
        self._flush_pending(snapshot["frame"])

    def completed_frame(self, frame):
        if getattr(getattr(self.session, 'spawn_cost_probe', None), 'mode', None) == 'baseline':
            if self.wait_probe is None:
                from tools.overworld.devtools_wait_probe import WaitProbe
                self.wait_probe = WaitProbe(self.session, self.hooks, self._guest_clock, self._clock,
                                           windows=((frame, frame + 3599),))
            if self.main_loop_probe is None:
                from tools.overworld.devtools_main_loop_probe import MainLoopProbe
                self.main_loop_probe = MainLoopProbe(self.session, self.hooks, self._guest_clock, self._clock,
                                                     windows=((frame, frame + 3599),))
        if self.wait_probe is not None:
            for row in self.wait_probe.completed_frame(frame):
                if len(self.pending) >= self.MAX_EVENTS:
                    raise NativeObservationError('stock wait probe event buffer is full')
                self._queue('stock-main-waits', {
                    'entry': row['branch']['native'],
                    'returned': row['mandatory']['returned']['native'],
                    'setupMode': 'prepared' if self.session.prepared else 'normal',
                    'returnValue': row['mandatory']['returned']['r0'],
                }, row)
        if self.main_loop_probe is not None:
            for row in self.main_loop_probe.completed_frame(frame):
                native = dict(actorFrame=row['actorFrame'], nativeCycle=row['nativeCycle'])
                self._queue('stock-main-loop-pacing', {
                    'entry': native, 'returned': native,
                    'setupMode': 'prepared' if self.session.prepared else 'normal',
                    'returnValue': 0,
                }, row)
        self.finalizations = {slot: receipt for slot, receipt in self.finalizations.items()
                              if self.queued_finalizations.get(slot) == receipt["finalizationId"]}
        self.queued_finalizations.clear()
        # A paused native-cycle endpoint may be past the last completed queue.
        # Expose only the count from that complete boundary, never a later call.
        self.player_step_count = self.player_steps_admitted
        self.player_step_frame = frame
        self._flush_pending(frame)

    def drain(self):
        events = list(self.ready)
        self.ready.clear()
        return events

    def snapshot(self, *, include_profiles=False):
        value = {"installedBeforeBoot": self.installed, "scope": "raw native observations; no acceptance verdict",
                "sequence": self.sequence, "eventsDropped": self.events_dropped,
                "profilesEvicted": self.profiles_evicted, "pendingCalls": len(self.contexts),
                "pendingUnframedEvents": len(self.pending), "error": self.hooks.error,
                "playerStepCount": self.player_step_count, "playerStepFrame": self.player_step_frame,
                "pendingPlayerSteps": self.player_steps_admitted - self.player_step_count,
                "coverageComplete": self.installed and not self.events_dropped and not self.profiles_evicted and self.hooks.error is None,
                "calls": deepcopy(self.calls), "profileFingerprints": list(self.profiles)}
        if include_profiles:
            value["resolvedProfiles"] = deepcopy(list(self.profiles.values()))
        if self.wait_probe is not None:
            value['stockWaitProbe'] = self.wait_probe.result()
        if self.main_loop_probe is not None:
            value['stockMainLoopPacing'] = self.main_loop_probe.result()
        return value

    def close(self):
        if self.main_loop_probe is not None:
            self.main_loop_probe.close()
        if self.wait_probe is not None:
            self.wait_probe.close()
        for token in self.tokens + self.return_tokens:
            self.hooks.remove(token)
        self.tokens.clear()
        self.return_tokens.clear()
        self.contexts.clear()
        self.spawn_contexts.clear()
        self.spawn_queue_contexts.clear()
        self.destination_contexts.clear()
        self.latest_destination_results.clear()
        self.pending_destination_scans.clear()
        self.policy_contexts.clear()
        self.finalization_contexts.clear()
        self.finalizations.clear()
        self.latest_finalization_results.clear()
        self.queued_finalizations.clear()
        self.latest_finalizations.clear()
        self.reposition_contexts.clear()
        self.reposition_call_sites.clear()
        self.spawn_height_trace = None
