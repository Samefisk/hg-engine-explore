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
import struct
from tools.overworld.devtools_spawn_cost_probe import gate as spawn_cost_gate


# Stock unk_0205FD20.s:sub_02060F24 copies current to previous, then reserves
# one cardinal next tile. This is admission, NOT rendered/terminal completion.
PLAYER_STEP_ADMISSION = 0x02060F24
PLAYER_WALK_COLLISION = 0x0205DA34
PLAYER_WALK_COLLISION_RETURN = 0x0205D4C6
SOUND_PLAY_SE = 0x0200604C
SOUND_STOP_SE = 0x02006154
PLAY_CRY = 0x02006218
HEART_BUBBLE = 0x02203A48
HEART_BUBBLE_DRAW = 0x02203DC0  # Retail ov01_02203DC0 draws the live stock bubble.
SPAWN_REFRESH_HEIGHT = 0x02061070
SPAWN_CREATE_OBJECT = 0x0205E2B4  # rom_gen.ld: CreateSpecialFieldObjectWithParams
MON_APPLY_FRIENDSHIP_MOD = 0x0206FE90
FRIENDSHIP_WAIT_WINDOW = (4639, 4644)
# Full retail unk_02023694.s:sub_02023F90 extent. The faulting load is +0xC.
MODEL_DATA_GETTER = 0x02023F90
MODEL_DATA_GETTER_CODE = bytes.fromhex("10b5041c01d101f0c1fa8834206810bd")
# Retail sub_02023EA4 writes the model draw flag at+0x24. Keep the
# caller before its NULL store switches the ARM9 to its Abort register bank.
MODEL_VISIBILITY_SETTER = 0x02023EA4
MODEL_VISIBILITY_SETTER_CODE = bytes.fromhex("38b5051c0c1c002d01d101f035fb24352c7038bd")
MODEL_POSITION_SETTER = 0x02023E50
MODEL_POSITION_SETTER_CODE = bytes.fromhex("38b5041c0d1c002c01d101f05ffb03cd03c42868206038bd")
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

# Actual native owners and ARM ABI in the published T74 build. NativeSpawn
# owns each real enqueue attempt, including the selected ordinary refill slot.
QUERY_SPAWN_READ_CAP = 8192  # Each leaf entry/return; separate from Cargo Tick.
QUERY_SPAWN_OWNERS = {'NativeSpawn': (34136452, 188, 'c22586382a702612439824cd3e6aa22b0f58c63a1c6e31dd5bf77e1237444376'),
 'OverworldEntryRoute_NativeControl': (34141536, 2692, 'aecd248fb30949a3c5da0012e0a3b5bf4098ea2231c4d143fd9784aa87ee8454'),
 'NativeFinalize': (34135844, 608, 'f219ee01435cbd6fdcb289865cfbadda53b6e157d7d4b99dfdfb4b9a16f73309')}

# Exact BL return sites in the full named owners above. Keep caller identity
# separate from the relocated owner address; test these against the real ELF.
QUERY_SPAWN_CALLERS = {
    "finalizer_from_spawn": 0x208e1fc,
    "finalizer_from_commit": 0x208f8ce,
    "spawn_from_refill": 0x208fe44,
    "spawn_from_single": 0x208ff6c,
}

# Current native ordinary helper selector; diagnostic-only in Baseline mode.
HELPER_SCAN_OWNERS = {'helper': ('helper', 'OverworldWildHelper_TryPrepareSpawn', 37516732, 692, '8756f89f0704c3f12d8b577e6d3b5fe41e8138cb661393b684260340c3948233'), 'scanner': ('helper', 'OverworldWildHelper_TryPickSpawnPositionForTerrain.constprop.0', 37516060, 540, '5d8c95f8405ad8f53ea50a756626ccd46bf21930a68f058a0582ad598c80ff55'), 'terrain': ('wild', 'OverworldWildSpawns_HelperTryGetSpawnTerrain', 37546176, 10, '0418f1a8c1e513ebba2acf6978689ef2ba5563e663e43c15063aa9989fa9c074'), 'occupied': ('wild', 'OverworldWildSpawns_HelperIsTileOccupied', 37546216, 10, 'c2ee4357f3042a1f799140c82aa656f96b2a366979185d75ad5a316e9a81c5e4'), 'near': ('wild', 'OverworldWildSpawns_HelperIsNearActiveSpawn', 37549760, 10, '10435cf6d8380f79342084426c0dc2f125339bfa9aeb9a8c4561d03daf024cab')}
HELPER_SCAN_TABLE_SHA = 'a57cfd3c60974525ee426235b2167ba79b988677ddd542fae31388c83020b46c'
# Exact BLX sites in the sealed ordinary scanner; its terrain local is u32.
HELPER_SCAN_CALL_SITES = {'terrain': 0x023C74B2, 'occupied': 0x023C74C8, 'near': 0x023C74D8}
HELPER_SCAN_TERRAIN_STACK_OFFSET = 0x28

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
                             "tick-profile-cost", "tick-conditions-cost", "tick-intent-boundary-cost",
                             "tick-issue-idle-cost", "tick-queued-combat-cost", "tick-prepare-conditions-cost",
                             "follower-spawn-cost", "follower-hop-start-cost", "spawn-queued", "spawn-refill-cost", "spawn-helper-cost",
                             "spawn-archive-cost", "spawn-finalized", "spawn-prepared", "spawn-motion",
                             "spawn-landing-height", "spawn-destination-search",
                             "spawn-candidate-cost", "spawn-query-admission-cost",
                             "spawn-surface-query-cost", "spawn-native-land-cost", "spawn-native-height-cost", "spawn-native-occupancy-cost",
                             "spawn-player-front-cost", "spawn-stack-clear-cost",
                             "spawn-metadata", "spawn-class-selection", "spawn-object-create",
                             "friendship-mod", "archive-open-cost", "archive-close-cost",
                             "archive-alloc-read-cost", "archive-read-cost", "archive-part-read-cost",
                             "archive-id-read-cost", "archive-id-alloc-read-cost",
                             "archive-sequential-read-cost"))

    def __init__(self, session, hooks, elf_code):
        self.session, self.hooks, self.elf_code = session, hooks, elf_code
        self.pending, self.ready = deque(), deque()
        self.profiles = OrderedDict()
        self.sequence = 0
        self.events_dropped = 0
        self.profiles_evicted = 0
        self.resolver_discovery = None
        self.contexts, self.spawn_contexts, self.policy_contexts = [], [], []
        self.playful_contexts, self.playful_step_contexts = [], []
        self.playful_step_id = 0
        self.playful_hearts = OrderedDict()
        self.spawn_queue_contexts = []
        self.query_spawn_identity = None
        self.query_spawn_read_bytes = 0
        self.query_spawn_tokens = []
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
        self.pool_fly_terrain = {}
        self.tokens, self.return_tokens = [], []
        self.calls = {}
        self.distance_count_cycle, self.distance_count = None, 0
        self.installed = False
        self.player_steps_admitted = 0
        self.player_step_count = 0
        self.player_step_frame = None
        self.wait_probe = None
        self.main_loop_probe = None
        self.null_model_getter = None
        self.null_model_visibility = None
        self.null_model_position = None
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
        if value.get("version") != 1 or value.get("running") is not True\
                or value.get("scope") != "nds-scheduler-ticks-not-cpu-or-instructions"\
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

    def _tap(self, label, address, expected, before, after, scope=None, *, resident=False, timed=False):
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
            if self._live_code(address, expected) != expected:
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
            if timed or label in self.TIMED_CALLS or (label == "behavior-resolved"
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
                if self._live_code(address, expected) != expected:
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

    def _live_code(self, address, expected):
        """Read only a span with exact linked/stock bytes in this ROM."""
        size = len(expected)
        if not size or not any(base <= address and address + size <= base + len(data)
                and data[address - base:address - base + size] == expected
                for base, data in self.session.code_regions):
            raise NativeObservationError("native code span differs from the packaged ROM")
        if 0x02000000 <= address < address + size <= 0x02400000:
            return self.session.read(address, size)
        # Resident code can be packaged in ITCM. This exception authorizes
        # only the exact code span above; public data reads keep their bounds.
        return self.session.rt.actor_memory_read(self.session.emu, address, size)

    def _install_null_model_getter(self, stock):
        self._install_null_model_entry(stock, "model-data-getter-null", MODEL_DATA_GETTER,
            MODEL_DATA_GETTER_CODE, "sub_02023F90", "null_model_getter", "model data getter")

    def _install_null_model_visibility(self, stock):
        self._install_null_model_entry(stock, "model-visibility-null", MODEL_VISIBILITY_SETTER,
            MODEL_VISIBILITY_SETTER_CODE, "sub_02023EA4", "null_model_visibility", "model visibility setter")

    def _install_null_model_position(self, stock):
        self._install_null_model_entry(stock, "model-position-null", MODEL_POSITION_SETTER,
            MODEL_POSITION_SETTER_CODE, "sub_02023E50", "null_model_position", "model position setter")

    def _install_null_model_entry(self, stock, label, address, expected, symbol, attribute, description):
        """Keep one failing entry, which cannot produce a normal return tap."""
        offset = address - 0x02000000
        if stock[offset:offset + len(expected)] != expected:
            raise NativeObservationError(f"stock {description} body differs")
        if not any(base <= address and address + len(expected) <= base + len(data)
                   and data[address - base:address - base + len(expected)] == expected
                   for base, data in self.session.code_regions):
            raise NativeObservationError(f"{description} body differs from the packaged ROM")
        self.calls[label] = {"address": address, "entrySha256": hashlib.sha256(expected).hexdigest(),
                             "entered": 0, "returned": 0, "nonmatchingEntries": 0}

        def entry():
            if getattr(self, attribute) is not None:
                return
            registers = self.session.emu.memory.register_arm9
            if registers.r0 & 0xFFFFFFFF:
                return
            if self._live_code(address, expected) != expected:
                self.calls[label]["nonmatchingEntries"] += 1
                raise NativeObservationError(f"{description} resident code identity differs")
            cpsr, pc = registers.cpsr & 0xFFFFFFFF, registers.pc & 0xFFFFFFFF
            if (cpsr & 0x3F != 0x3F or (pc - 4) & 0xFFFFFFFF != address
                    or getattr(self.hooks, "current_callback", None)
                        != {"address": address, "size": 2}):
                raise NativeObservationError(f"{description} is not an ARM9 Thumb/System entry")
            values = {key: getattr(registers, key) & 0xFFFFFFFF
                      for key in (*("r" + str(i) for i in range(8)), "sp", "lr", "pc", "cpsr")}
            stack = {"address": values["sp"], "requestedBytes": 32, "readBytes": 0}
            try:
                raw = public_bytes(self.session, values["sp"], 32)
                stack.update(known=True, readBytes=32, rawHex=raw.hex(),
                             words=list(struct.unpack("<8I", raw)))
            except Exception as error:
                # An unavailable stack cannot erase the observed null call.
                # The null call still fails the observer below.
                stack.update(known=False, reason=f"{type(error).__name__}: {error}")
            receipt = {
                "schemaVersion": 1, "diagnosticOnly": True, "acceptedProof": False,
                "boundary": "native-function-entry-before-instruction",
                "symbol": symbol, "address": address,
                "codeSha256": hashlib.sha256(expected).hexdigest(), "codeBytes": len(expected),
                **self._clock(), "setupMode": "prepared" if self.session.prepared else "normal",
                "registers": values, "callerReturn": values["lr"], "systemSp": values["sp"],
                "stack": stack, "maximumReceipts": 1,
                "scope": f"first null field 3D {description} argument; raw caller, no owner inference",
            }
            setattr(self, attribute, receipt)
            self.calls[label]["entered"] += 1
            # Shared hooks retain the first error until the native cycle ends;
            # they cannot stop this guest instruction. Keep the entry receipt
            # separate from completed-frame observations for fault diagnostics.
            raise NativeObservationError(f"stock {description} received NULL; entry receipt retained")

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
        from tools.overworld.devtools_mount_forward_hop_observer import install_mount_forward_hop
        self.mount_forward_hop = install_mount_forward_hop(self, linked)

        linked("spawn-finalized", wild_file, rt.WILD_SYMBOLS,
               "OverworldWildSpawns_FinalizePreparedSpawn", self._finalize_before, self._finalize_after)
        # Query relocates at Field admission; install this real native leaf
        # after exact lease discovery, without requiring an emitted Wild wrapper.
        address, size, sha = QUERY_SPAWN_OWNERS["NativeSpawn"]
        self.calls["spawn-queued"] = dict(address=address, bodyBytes=size,
            entrySha256=sha, entered=0, returned=0, nonmatchingEntries=0,
            awaitingQueryLease=True)
        linked("spawn-query-discovery", wild_file, rt.WILD_SYMBOLS,
               "OverworldWildSpawns_QueryAddon", lambda: {}, self._query_spawn_discover_after,
               scope=self._query_spawn_discovery_needed)
        battle_start = "OverworldWildSpawns_TryStartBattleForSlot"
        battle_request = "OverworldWildSpawns_RequestBattleScript"
        # The original tap keeps its field/state/slot ABI when emitted. The
        # fallback is state/field/slot and returns TRUE only after the pending
        # identity is primed and RequestBattleScript succeeds.
        if battle_request in rt.WILD_SYMBOLS:
            battle_symbol = battle_request
            self._battle_request_state_first = False
        elif battle_start in rt.WILD_SYMBOLS:
            battle_symbol = battle_start
            self._battle_request_state_first = True
        else:
            raise NativeObservationError("wild battle request symbol unavailable")
        linked("wild-battle-request", wild_file, rt.WILD_SYMBOLS,
               battle_symbol, self._battle_request_before,
               self._battle_request_after)
        cost_scope = lambda: getattr(getattr(self.session, "spawn_cost_probe", None), "mode", None) == "baseline"
        helper_file = rt.REPO / "build/overworld_wild_helper_overlay_linked.o"
        helper_symbols = rt.linked_symbols(helper_file)
        # Optional raw distance-maintenance receipt, within the existing Throw
        # recording window. Arguments come from the authenticated native helper;
        # the Wild wrapper is inlined in the current production build.
        linked("distance-maintenance", helper_file, helper_symbols,
               "OverworldWildHelper_DespawnFarEncounters",
               self._distance_before, self._distance_after,
               scope=lambda: bool(getattr(self.session, "_throw_interactions_window", False)))
        for label, path, symbols, name in (
                ("population-frame-cost", wild_file, rt.WILD_SYMBOLS, "OverworldWildSpawns_FrameMovementTask"),
                ("population-movement-cost", wild_file, rt.WILD_SYMBOLS, "OverworldWildSpawns_TickMovementParams.constprop.0"),
                ("population-step-cost", wild_file, rt.WILD_SYMBOLS, "OverworldWildSpawns_OverlayOnPlayerStep"),
                ("follower-spawn-cost", wild_file, rt.WILD_SYMBOLS, "OverworldWildSpawns_TrySpawnFollower"),
                ("follower-hop-start-cost", wild_file, rt.WILD_SYMBOLS, "OverworldWildSpawns_TryStartDirectedBehaviorHopCommand"),
                ("spawn-refill-cost", wild_file, rt.WILD_SYMBOLS, "OverworldWildSpawns_TryRefill"),
                ("spawn-helper-cost", helper_file, helper_symbols, "OverworldWildHelper_TryPrepareSpawn"),
                ("spawn-archive-cost", wild_file, rt.WILD_SYMBOLS, "OverworldWildSpawns_HelperLoadArchiveData")):
            linked(label, path, symbols, name,
                   self._helper_spawn_before if label == "spawn-helper-cost" else self._refill_cost_before,
                   self._helper_spawn_after if label == "spawn-helper-cost" else self._refill_cost_after,
                   scope=cost_scope)
        # Optional per-actor movement cost spans; skipped when a build inlines them.
        for label, name in (
                ("tick-profile-cost", "OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot"),
                ("tick-conditions-cost", "OverworldWildSpawns_EvaluateConditionsForSlot"),
                ("tick-intent-boundary-cost", "OverworldWildSpawns_ResolveConditionsAtIntentBoundary"),
                ("tick-issue-idle-cost", "OverworldWildSpawns_IssueIdleIntent"),
                ("tick-queued-combat-cost", "OverworldWildSpawns_ApplyQueuedCombat"),
                ("tick-prepare-conditions-cost", "OverworldWildSpawns_PrepareConditionsForSlot")):
            if name in rt.WILD_SYMBOLS:
                linked(label, wild_file, rt.WILD_SYMBOLS, name, self._refill_cost_before,
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
        linked("playful-sequence", wild_file, rt.WILD_SYMBOLS,
               "OverworldWildSpawns_TryStartChainPauseAction",
               self._playful_sequence_before, self._playful_sequence_after)
        linked("playful-step", wild_file, rt.WILD_SYMBOLS,
               "OverworldWildSpawns_StartNextSpotEmoteStep",
               self._playful_step_before, self._playful_step_after)
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
        # Diagnostic only: split one resumed scanner's inclusive candidate
        # cost without changing its queries, clocks, or acceptance rules.
        destination_cost_scope = lambda: cost_scope() and bool(self.destination_contexts)
        for label, path, symbols, name in (
                ("spawn-candidate-cost", wild_file, rt.WILD_SYMBOLS,
                 "OverworldWildSpawns_ClassifyBehaviorHopLandingTile"),
                ("spawn-query-admission-cost", wild_file, rt.WILD_SYMBOLS,
                 "OverworldWildSpawns_QueryAddon"),
                ("spawn-surface-query-cost", runtime_file, rt.linked_symbols(runtime_file),
                 "OverworldWildRuntime_QuerySurface"),
                ("spawn-native-land-cost", wild_file, rt.WILD_SYMBOLS,
                 "OverworldWildSpawns_IsLandMapTile"),
                ("spawn-native-height-cost", runtime_file, rt.linked_symbols(runtime_file),
                 "OverworldWildRuntime_ResolveBaseYAt"),
                ("spawn-native-occupancy-cost", rt.REPO / "build/pokemon_move_history_overlay_linked.o",
                 rt.linked_symbols(rt.REPO / "build/pokemon_move_history_overlay_linked.o"),
                 "OverworldWildOccupancy_Query"),
                ("spawn-player-front-cost", helper_file, helper_symbols,
                 "OverworldSpawnSpatial_IsPlayerFrontTile"),
                ("spawn-stack-clear-cost", rt.REPO / "build/linked.o",
                 rt.linked_symbols(rt.REPO / "build/linked.o"), "memset")):
            linked(label, path, symbols, name, self._refill_cost_before,
                   self._refill_cost_after, scope=destination_cost_scope)
        linked("chain-motion-request", runtime_file, rt.linked_symbols(runtime_file),
               "OverworldWildRuntime_RequestMotion", self._chain_request_before, self._chain_request_after,
               scope=lambda: bool(self.reposition_contexts))
        task6_file = rt.REPO / "build/pokemon_move_history_task6_overlay_linked.o"
        linked("chain-hop-plan", task6_file, rt.linked_symbols(task6_file),
               "OverworldActorHopPlanner_Plan", self._chain_plan_before, self._chain_plan_after,
               scope=lambda: bool(self.reposition_contexts)
               and self.reposition_contexts[-1]["_activeStart"] is not None)
        # The scanner now uses the same real native Landing classifier as
        # movement. The old private BOOL metatile matcher has no emitted body.
        # Do not claim its former chain-terrain detail from an addon callback.
        linked("spawn-destination-query", wild_file, rt.WILD_SYMBOLS,
               "OverworldWildSpawns_ClassifyBehaviorHopLandingTile",
               self._destination_query_before, self._destination_query_after,
               scope=lambda: bool(self.destination_contexts), resident=True)
        for label, name in (("surface", "QuerySurface"),
                            ("objects", "IsTileOccupiedByObject"),
                            ("nonplayer", "IsTileOccupiedByNonPlayerObject")):
            linked("chain-landing-" + label, wild_file, rt.WILD_SYMBOLS,
                   "OverworldWildSpawns_" + name,
                   lambda kind=label: self._landing_detail_before(kind),
                   self._landing_detail_after, scope=self._landing_detail_scope, resident=True)
        # rom_gen.ld / vanilla GF_Rand: observe returns only while a relevant
        # public policy call owns the draw. Never call or alter the RNG.
        address = 0x0201FD44
        stock = (rt.REPO / "base/arm9.bin").read_bytes()
        # Named retail filesystem.c entries, checked against this packaged ROM.
        # Observe all callers: map-object assets can load after SpawnOne returns.
        # Arguments are raw API registers; do not guess a NARC id from a handle.
        # NARC_ReadFile uses r0=NARC*, r1=size, r2=destination and returns void.
        # Its tail call retains the original caller LR for the inclusive span.
        for label, address in (("archive-open-cost", 0x02007688),
                               ("archive-close-cost", 0x0200770C),
                               ("archive-alloc-read-cost", 0x0200771C),
                               ("archive-read-cost", 0x0200778C),
                               ("archive-part-read-cost", 0x0200782C),
                               ("archive-sequential-read-cost", 0x020078D8),
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
                  lambda: self.policy_contexts[-1] if self.policy_contexts else self.playful_contexts[-1],
                  self._rng_after,
                  scope=lambda: bool(self.policy_contexts or self.playful_contexts))
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
        # Stock PlaySE/StopSE receipts identify the actual field sound. These
        # hooks only read calls; they do not play, stop, or replace any audio.
        for label, address in (("sound-play", SOUND_PLAY_SE), ("sound-stop", SOUND_STOP_SE)):
            self._tap(label, address,
                      stock[address - 0x02000000:address - 0x02000000 + 32],
                      lambda: {"sequenceId": self.session.emu.memory.register_arm9.r0 & 0xFFFF,
                               "caller": self.session.emu.memory.register_arm9.lr & ~1},
                      lambda data, context: data, resident=True)
        self._tap("playful-cry", PLAY_CRY,
                  stock[PLAY_CRY - 0x02000000:PLAY_CRY - 0x02000000 + 32],
                  self._playful_cry_before, self._playful_effect_after,
                  scope=lambda: bool(self.playful_step_contexts), resident=True)
        overlay = self.session.dialogue_overlay_regions.get(1)
        if overlay is None or not overlay[0] <= HEART_BUBBLE <= overlay[0] + len(overlay[1]) - 32:
            raise NativeObservationError("stock heart effect is absent from packaged overlay 1")
        bubble_code = overlay[1][HEART_BUBBLE - overlay[0]:HEART_BUBBLE - overlay[0] + 32]
        self._tap("playful-heart", HEART_BUBBLE, bubble_code,
                  self._playful_heart_before, self._playful_heart_after,
                  scope=lambda: bool(self.playful_step_contexts))
        if not overlay[0] <= HEART_BUBBLE_DRAW <= overlay[0] + len(overlay[1]) - 32:
            raise NativeObservationError("stock heart draw is absent from packaged overlay 1")
        draw_code = overlay[1][HEART_BUBBLE_DRAW - overlay[0]:HEART_BUBBLE_DRAW - overlay[0] + 32]
        self._tap("playful-heart-draw", HEART_BUBBLE_DRAW, draw_code,
                  self._playful_heart_draw_before, self._playful_effect_after,
                  scope=lambda: self.session.emu.memory.register_arm9.r0 in self.playful_hearts)
        self._tap("safety-bubble", HEART_BUBBLE, bubble_code,
                  self._safety_bubble_before, self._safety_bubble_after)
        from tools.overworld.devtools_fly_landing_cost import FlyLandingCost
        self.fly_landing_cost = FlyLandingCost(self)
        self._install_null_model_getter(stock)
        self._install_null_model_visibility(stock)
        self._install_null_model_position(stock)
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
        arg0, arg1, slot = (getattr(regs, key) & 0xFFFFFFFF
                            for key in ("r0", "r1", "r2"))
        state, field = (arg0, arg1) if self._battle_request_state_first\
            else (arg1, arg0)
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
        if self._live_code(address, cache[address]) != cache[address]:
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
            # The Query add-on Landing calls the shared occupancy query at
            # 0x023C0184 directly, not the Wild wrappers tapped above.
            stage = "accepted-occupancy-unobserved"
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
                  "laneHex": public_bytes(self.session, word(4), 80).hex()}
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
        record = {"kind": kind, "laneHex": public_bytes(self.session, lane, 80).hex(),
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
            if address == PLAYER_WALK_COLLISION_RETURN - 4:
                # armips/asm/overworld_mount.s patches this BL to the fixed
                # PlayerHealthContact_StockCollisionEntry at 0x01FFC160.
                # A later build may change base/arm9.bin while this session
                # still owns its earlier ROM. Bind the packaged caller to the
                # two exact supported call sites and the vanilla continuation.
                matches = [data[address - base:address - base + size]
                           for base, data in self.session.code_regions
                           if base <= address and address + size <= base + len(data)]
                allowed = []
                for target in (PLAYER_WALK_COLLISION, 0x01FFC160):
                    offset = target - PLAYER_WALK_COLLISION_RETURN
                    allowed.append(struct.pack("<HH", 0xF000 | ((offset >> 12) & 0x7FF),
                                               0xF800 | ((offset >> 1) & 0x7FF))
                                   + bytes.fromhex("041c301c"))
                if len(matches) != 1 or matches[0] not in allowed:
                    raise NativeObservationError("walking collision caller differs from packaged ROM")
                expected = matches[0]
            if len(expected) != size or not any(
                    base <= address and address + size <= base + len(data)
                    and data[address - base:address - base + size] == expected
                    for base, data in self.session.code_regions):
                raise NativeObservationError("walking collision full body/caller differs from packaged ROM")
            identity.append((address, expected))
        self.player_collision_identity = tuple(identity)

    def _check_player_collision_identity(self):
        for address, expected in self.player_collision_identity:
            if self._live_code(address, expected) != expected:
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
        if [after["x"], after["y"]] != target\
                or [after["x_prev"], after["y_prev"]] != [before["x"], before["y"]]\
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
        if slot >= 10 or slot == 7:
            return None
        # Both authenticated linked functions have this exact five-argument
        # AAPCS signature. include/overworld_wild_helper.h owns the value layout:
        # position(12), encounter(8), then startup(10). No private actor offsets.
        return {"slot": slot, "terrain": regs.r2 & 0xFFFFFFFF,
                "statePointer": regs.r0 & 0xFFFFFFFF, "fieldPointer": regs.r1 & 0xFFFFFFFF,
                "preparedPointer": int.from_bytes(public_bytes(self.session, regs.sp, 4), "little"),
                "worldContext": self._world_context()}

    def _distance_state(self, value):
        from tools.overworld.devtools_pokemon_combat_observer import (
            WILD_FIELD_OFFSET, WILD_RUNTIME_SIZE, RUNTIME_THROW_OFFSET,
        )
        # No guessed private presentation offset: r2/r3 are the real typed
        # presentation/telemetry arguments of this authenticated helper call.
        owner = public_bytes(self.session, value["statePointer"] + WILD_FIELD_OFFSET, 8)
        field = int.from_bytes(owner[:4], "little")
        runtime = int.from_bytes(owner[4:], "little")
        if field != value["fieldPointer"] or runtime != value["runtimePointer"]:
            raise NativeObservationError("distance maintenance lost its runtime owner")
        presentation = public_bytes(self.session, value["presentationPointer"], 54)
        telemetry = public_bytes(self.session, value["telemetryPointer"], 336)
        claim = public_bytes(self.session, runtime + RUNTIME_THROW_OFFSET, 16)
        magic = int.from_bytes(telemetry[:4], "little")
        if magic not in (0, 0x4F574450) or telemetry[6] >= 8:
            raise NativeObservationError("distance telemetry layout differs")
        return {"lastKnownX": [int.from_bytes(presentation[i:i + 2], "little", signed=True)
                               for i in range(0, 20, 2)],
                "lastKnownY": [int.from_bytes(presentation[i:i + 2], "little", signed=True)
                               for i in range(20, 40, 2)],
                "farSamples": list(presentation[40:50]),
                "managerRestoreMask": int.from_bytes(presentation[50:52], "little"),
                "distanceDespawnPendingMask": int.from_bytes(presentation[52:54], "little"),
                "throwState": {"targets": list(claim[:10]),
                    "targetMask": int.from_bytes(claim[10:12], "little"),
                    "carrierMask": int.from_bytes(claim[12:14], "little"),
                    "recoveringMask": int.from_bytes(claim[14:16], "little")},
                "telemetrySequence": int.from_bytes(telemetry[4:6], "little"),
                "telemetryWriteIndex": telemetry[6], "telemetryHex": telemetry.hex(),
                "readBytes": 414}

    def _distance_before(self):
        from tools.overworld.devtools_pokemon_combat_observer import (
            _interaction_layout, WILD_FIELD_OFFSET, WILD_RUNTIME_SIZE,
        )
        regs = self.session.emu.memory.register_arm9
        native = getattr(self, "_distance_native", None)
        if native is None:
            from tools.overworld.devtools_field_cleanup import symbol as native_symbol
            path = self.session.rt.REPO / "build/overworld_wild_helper_overlay_linked.o"
            native = native_symbol(path.read_bytes(),
                "OverworldWildHelper_DespawnFarEncounters", 2, expected_size=332)
            code = native[2]
            if (code[0x18:0x1A] != bytes.fromhex("2836")
                    or code[0xE0:0xE2] != bytes.fromhex("a18e")
                    or code[0xE4:0xE6] != bytes.fromhex("a186")
                    or code[0x132:0x134] != bytes.fromhex("0a2d")):
                raise NativeObservationError("distance native presentation/slot layout differs")
            self._distance_native = native
        if self._live_code(native[0], native[2]) != native[2]:
            raise NativeObservationError("distance native helper is not current")
        world = self._world_context()
        field, state, presentation, telemetry = [getattr(regs, "r" + str(i)) & 0xFFFFFFFF for i in range(4)]
        if field != world["fieldPointer"] or not field or state != world["statePointer"]:
            raise NativeObservationError("distance maintenance arguments differ from current Field")
        # Existing packaged getter admission proves the E0/E4 owner ABI before
        # following its pointer; every call also checks the loaded getter body.
        getter = _interaction_layout(self.session)["getter"]
        if self._live_code(getter[0], getter[2]) != getter[2]:
            raise NativeObservationError("distance runtime getter is not current")
        owner = public_bytes(self.session, state + WILD_FIELD_OFFSET, 8)
        runtime = int.from_bytes(owner[4:], "little")
        if (runtime & 3 or not 0x02000000 <= runtime <= 0x02400000 - WILD_RUNTIME_SIZE
                or int.from_bytes(owner[:4], "little") != field
                or not runtime <= presentation < presentation + 54 <= telemetry
                or not telemetry + 336 <= runtime + WILD_RUNTIME_SIZE):
            raise NativeObservationError("distance maintenance argument spans differ")
        cycle = self._clock().get("nativeCycle")
        if type(cycle) is not int or cycle < 0:
            raise NativeObservationError("distance maintenance native cycle is invalid")
        if self.distance_count_cycle is not None and cycle < self.distance_count_cycle:
            raise NativeObservationError("distance maintenance native cycle moved backwards")
        if cycle != self.distance_count_cycle:
            self.distance_count_cycle, self.distance_count = cycle, 0
        if self.distance_count >= 64:
            raise NativeObservationError("distance maintenance receipt budget exceeded")
        self.distance_count += 1
        stack = public_bytes(self.session, regs.sp & 0xFFFFFFFF, 12)
        value = {"fieldPointer": field, "statePointer": state, "runtimePointer": runtime,
                 "presentationPointer": presentation, "telemetryPointer": telemetry,
                 "hardProtectedMask": int.from_bytes(stack[:4], "little"),
                 "movementDeferredMask": int.from_bytes(stack[4:8], "little"),
                 "resetSlotPointer": int.from_bytes(stack[8:12], "little"),
                 "worldContext": world}
        if value["hardProtectedMask"] > 0xFFFF or value["movementDeferredMask"] >> 10:
            raise NativeObservationError("distance maintenance mask width differs")
        value["before"] = self._distance_state(value)
        return value

    def _distance_after(self, value, context):
        if self._world_context() != value["worldContext"]:
            raise NativeObservationError("distance maintenance changed current Field context")
        after = self._distance_state(value)
        if (after["telemetrySequence"] - value["before"]["telemetrySequence"]) & 0xFFFF > 8:
            raise NativeObservationError("distance maintenance overwrote its eight-record receipt")
        return {**value, "after": after, "scope": "native scheduled distance-maintenance entry/return",
                "diagnosticOnly": True, "acceptedProof": False, "argumentSpanReadBytes": 848}

    def _helper_spawn_layout(self):
        from tools.overworld.devtools_field_cleanup import symbol
        from tools.overworld.devtools_runtime import _elf_code
        cached = getattr(self, "helper_spawn_layout", None)
        if cached is not None:
            return cached
        build = self.session.rt.REPO / "build"
        paths = {home: build / file for home, file in
                 (("wild", "overworld_wild_spawns_overlay_linked.o"),
                  ("helper", "overworld_wild_helper_overlay_linked.o"))}
        owners = {}
        for key, (home, name, address, size, sha) in HELPER_SCAN_OWNERS.items():
            linked = symbol(paths[home].read_bytes(), name, 2, expected_size=size)
            body = _elf_code(paths[home], address, size)
            if (linked[:2] != (address, size) or linked[2] != body
                or hashlib.sha256(body).hexdigest() != sha
                or self.session.packaged_code(address, size) != body):
                raise NativeObservationError("spawn helper full native owner differs: " + key)
            owners[key] = (address, body)
        cursor = symbol(paths["helper"].read_bytes(),
                        "sOverworldWildHelperSpawnPositionCursor", 1, ".text", 4)
        table = symbol(paths["wild"].read_bytes(), "sOverworldWildSpawnPrepCallbacks", 1,
                       expected_size=36)
        body = _elf_code(paths["wild"], table[0], table[1])
        # The fixed helper linker folds this source BSS object into .text.
        cursor_initial = _elf_code(paths["helper"], cursor[0], cursor[1])
        if (cursor[:2] != (0x023C7D2A, 4) or table[:2] != (0x023CCFD8, 36)
                or cursor_initial != bytes(4)
                or hashlib.sha256(body).hexdigest() != HELPER_SCAN_TABLE_SHA
                or struct.unpack_from("<3I", body, 4) != tuple(
                    owners[key][0] | 1 for key in ("terrain", "occupied", "near"))
                or self.session.packaged_code(table[0], 36) != body):
            raise NativeObservationError("spawn helper callback table or cursor owner differs")
        cached = dict(owners=owners, cursor=cursor[0], table=table[0], tableBytes=body)
        self.helper_spawn_layout = cached
        for key in ("terrain", "occupied", "near"):
            address, _ = owners[key]
            self._tap("spawn-helper-" + key, address,
                      self.elf_code(paths["wild"], address, 32),
                      lambda key=key: self._helper_candidate_before(key),
                      self._helper_candidate_after,
                      scope=lambda: getattr(getattr(self.session, "spawn_cost_probe", None),
                                            "mode", None) == "baseline"
                          and self._helper_candidate_parent() is not None, resident=True)
        return cached

    def _helper_candidate_parent(self):
        for context in reversed(self.contexts):
            value = context.get("data")
            if isinstance(value, dict) and value.get("helperDiagnostic") is True:
                return value
        return None

    def _helper_scan_auth(self, value, *, full=False):
        layout = value["_layout"]
        state = value["worldContext"]["statePointer"]
        owner = public_bytes(self.session, state + 0xE0, 8)
        field, runtime = struct.unpack("<2I", owner)
        if (self._world_context() != value["worldContext"]
                or field != value["worldContext"]["fieldPointer"]
                or runtime & 3 or not 0x02000000 <= runtime < 0x02400000
                or public_bytes(self.session, value["prepContext"], 12) != value["prepContextBytes"]
                or public_bytes(self.session, layout["table"], 36) != layout["tableBytes"]):
            raise NativeObservationError("spawn helper parent, Field or callback table changed")
        if full:
            for key in ("helper", "scanner"):
                address, body = layout["owners"][key]
                if self._live_code(address, body) != body:
                    raise NativeObservationError("spawn helper full live owner differs: " + key)

    def _helper_scan_cursor(self, layout):
        address = layout["cursor"]
        raw = public_bytes(self.session, address & ~3, 8)
        result = list(struct.unpack_from("<2H", raw, address & 3))
        if any(value > 441 for value in result):
            raise NativeObservationError("spawn helper cursor is outside its typed ring")
        return result

    def _helper_spawn_before(self):
        value = self._refill_cost_before()
        args = value["arguments"]
        # Fishing/Headbutt have different selectors; keep their old raw receipt.
        if args[2] not in (0, 1):
            return value
        layout = self._helper_spawn_layout()
        raw = public_bytes(self.session, args[1], 12)
        state, field, terrain = struct.unpack("<3I", raw)
        if (args[0] != layout["table"] or args[3] >= 10
                or field & 3 or not 0x02000000 <= field < 0x02400000
                or (state, field, terrain) != (value["worldContext"]["statePointer"],
                    value["worldContext"]["fieldPointer"], args[2])):
            raise NativeObservationError("spawn helper typed parent differs")
        value.update(helperDiagnostic=True, _layout=layout, prepContext=args[1],
                     prepContextBytes=raw, requestedTerrain=terrain, slot=args[3],
                     candidates=[])
        self._helper_scan_auth(value, full=True)
        value["cursorBefore"] = self._helper_scan_cursor(layout)
        return value

    def _helper_spawn_after(self, value, context):
        result = self._refill_cost_after(value, context)
        if value.get("helperDiagnostic") is not True:
            return result
        self._helper_scan_auth(value, full=True)
        if (context["returnValue"] not in (0, 1, 2)
                or any(row["next"] != "done" for row in value["candidates"])):
            raise NativeObservationError("spawn helper return or child order differs")
        result = {key: item for key, item in result.items()
                  if key not in ("_layout", "prepContextBytes")}
        result.update(cursorAfter=self._helper_scan_cursor(value["_layout"]),
                      candidateScope="ordinary Land/Surf native helper selector",
                      maximumCandidates=32, diagnosticOnly=True, acceptedProof=False)
        return result

    def _helper_candidate_before(self, key):
        value = self._helper_candidate_parent()
        if value is None:
            raise NativeObservationError("spawn helper candidate has no live parent")
        self._helper_scan_auth(value)
        regs = self.session.emu.memory.register_arm9
        layout = value["_layout"]
        address, body = layout["owners"][key]
        if self._live_code(address, body) != body:
            raise NativeObservationError("spawn helper callback live full body differs")
        site = (regs.lr & ~1) - 2
        scanner, scan_body = layout["owners"]["scanner"]
        offset = site - scanner
        if (site != HELPER_SCAN_CALL_SITES[key]
                or offset < 0 or offset > len(scan_body) - 2 or offset & 1):
            raise NativeObservationError("spawn helper callback caller is outside its scanner")
        opcode = struct.unpack_from("<H", scan_body, offset)[0]
        register = (opcode >> 3) & 15
        if (opcode & 0xFF87 != 0x4780 or register >= 8
                or getattr(regs, "r" + str(register)) & 0xFFFFFFFF != address | 1
                or regs.r0 & 0xFFFFFFFF != value["prepContext"]):
            raise NativeObservationError("spawn helper callback binding or caller differs")
        point = [struct.unpack("<i", struct.pack("<I", getattr(regs, name) & 0xFFFFFFFF))[0]
                 for name in ("r1", "r2")]
        rows = value["candidates"]
        if key == "terrain":
            if len(rows) >= 32 or (rows and rows[-1]["next"] != "done"):
                raise NativeObservationError("spawn helper candidate limit or order differs")
            output = regs.r3 & 0xFFFFFFFF
            stack = regs.sp & 0xFFFFFFFF
            # At callback entry the sealed scanner passes aligned SP+0x28;
            # its later LDR reads the complete u32 local. Keep public bounds.
            if (stack & 3 or output & 3 or output != stack + HELPER_SCAN_TERRAIN_STACK_OFFSET
                    or not (0x02000000 <= output <= 0x023FFFFC
                        or 0x027E0000 <= output <= 0x027E3FBC)):
                raise NativeObservationError(
                    f"spawn helper terrain output pointer differs: output={output:#x}, "
                    f"sp={stack:#x}, caller={site:#x}")
            row = dict(point=point, next="terrain", terrainPointer=output)
            rows.append(row)
        else:
            if (not rows or rows[-1]["next"] != key or rows[-1]["point"] != point
                or (key == "near" and regs.r3 & 0xFFFFFFFF != 3)):
                raise NativeObservationError("spawn helper child point, radius or order differs")
            row = rows[-1]
        return dict(parent=value, row=row, child=key, caller=site)

    def _helper_candidate_after(self, child, context):
        value, row, key = child["parent"], child["row"], child["child"]
        if (self._helper_candidate_parent() is not value or value["candidates"][-1] is not row
                or row["next"] != key or context["returnValue"] not in (0, 1)):
            raise NativeObservationError("spawn helper child lost its parent or native return")
        self._helper_scan_auth(value)
        address, body = value["_layout"]["owners"][key]
        if self._live_code(address, body) != body:
            raise NativeObservationError("spawn helper callback full body changed on return")
        answer = context["returnValue"]
        row[key + "Return"] = answer
        if key == "terrain":
            if not answer:
                row.update(next="done", reason="terrain-unavailable")
            else:
                output = row["terrainPointer"]
                terrain = struct.unpack("<I", public_bytes(self.session, output, 4))[0]
                if terrain not in (0, 1):
                    raise NativeObservationError("spawn helper returned terrain enum differs")
                row["terrain"] = terrain
                row.update(next="occupied" if terrain == value["requestedTerrain"] else "done")
                if row["next"] == "done":
                    row["reason"] = "terrain-mismatch"
        elif key == "occupied":
            row.update(next="done" if answer else "near")
            if answer:
                row["reason"] = "occupied"
        else:
            row.update(next="done", reason="near-active" if answer else "selected")
        return None  # One bounded candidate list is retained by the helper receipt.

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
        if not any(item is parent for item in self.finalization_contexts + self.spawn_contexts)\
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
        if not self.destination_contexts or self.destination_contexts[-1] is not value\
                or not self.finalization_contexts\
                or self.finalization_contexts[-1]["finalizationId"] != value["finalizationId"]\
                or self._world_context() != value["worldContext"]\
                or context["returnValue"] not in (0, 1):
            raise NativeObservationError("spawn destination search lost its finalizer owner or world")
        self.destination_contexts.pop()
        result = {**value, "outputPositionHex": public_bytes(
            self.session, value["positionPointer"], 8).hex()}
        if value["spawnAttemptId"] is not None and self.spawn_queue_contexts:
            self.latest_destination_results[value["spawnAttemptId"]] = deepcopy(result)
        return result

    def _destination_query_before(self):
        parent = self.destination_contexts[-1]
        regs = self.session.emu.memory.register_arm9
        self._chain_caller("OverworldWildSpawns_TryPickSpawnDestinationMask")
        words = self._chain_words(4)
        if (regs.r0 & 0xFFFFFFFF, regs.r1 & 0xFFFFFFFF,
                regs.r2 & 0xFFFFFFFF, regs.r3 & 0xFFFF) != (
                    0, 0xFFFFFFFF, parent["worldContext"]["fieldPointer"],
                    parent["destinationMask"])\
                or words[2:] != [0xFFFFFFFF, 0xFFFFFFFF]\
                or self._world_context() != parent["worldContext"]:
            raise NativeObservationError("spawn destination query differs from its scanner owner")
        parent["candidateQueryCount"] += 1
        if parent["candidateQueryCount"] > 255:
            raise NativeObservationError("spawn destination query count exceeded its bounded call")
        return parent

    def _destination_query_after(self, value, context):
        if not self.destination_contexts or self.destination_contexts[-1] is not value\
                or context["returnValue"] not in range(len(MOTION_DECISIONS))\
                or self._world_context() != value["worldContext"]:
            raise NativeObservationError("spawn destination query lost its scanner owner")
        return None

    def _query_spawn_discovery_needed(self):
        if self.finalization_contexts or self.spawn_queue_contexts:
            return False
        identity = self.query_spawn_identity
        if identity is None:
            return True
        owner = identity["owner"]
        field = struct.unpack_from("<I", bytes.fromhex(owner["rawHex"]), 12)[0]
        world = self._world_context()
        return (world["fieldPointer"], world["fieldEpoch"], world["mapGeneration"]) != (
            field, owner["fieldEpoch"], owner["mapGeneration"]) or public_bytes(
                self.session, owner["stateAddress"], 28).hex() != owner["rawHex"]

    def _query_spawn_discover_after(self, value, context):
        if context["returnValue"] == 0:
            return None
        # Full image authentication is performed at discovery, independently
        # of the opt-in Throw recorder. Subsequent taps retain this exact lease.
        import ndspy.narc
        import ndspy.rom
        from tools.overworld.devtools_query_observer import (
            authenticate_loaded_query_functions, sealed_package, relocated_image,
            native_entry_bindings, BASE, ENTRY)
        from tools.overworld.devtools_field_cleanup import symbol
        rt = self.session.rt
        directory = rt.REPO / "build/overworld_query_code_addon"
        elf = (directory / "image.elf").read_bytes()
        staged = (directory / "query.bin").read_bytes()
        member = ndspy.narc.NARC(ndspy.rom.NintendoDSRom.fromFile(str(self.session.rom))
                                .getFileByName("a/0/2/8")).files[21]
        # The generic cleanup symbol reader caps small functions at 2048B.
        # Keep it for the two leaf owners; bind the exact larger Control owner
        # through the existing typed FUNC/extent and executable ELF readers.
        from tools.overworld.devtools_runtime import _elf_function_extent
        small_owners = {name: pin for name, pin in QUERY_SPAWN_OWNERS.items()
                        if name != "OverworldEntryRoute_NativeControl"}
        owner = authenticate_loaded_query_functions(self.session, elf, staged, member, small_owners)
        if owner["entry"] != context["returnValue"] or self.finalization_contexts:
            raise NativeObservationError("automatic spawn Query discovery lost its current owner")
        _, image, receipt = sealed_package(elf, staged, member)
        expected = relocated_image(image, receipt, owner["entry"])
        name = "OverworldEntryRoute_NativeControl"
        address, size, digest = QUERY_SPAWN_OWNERS[name]
        body = self.elf_code(directory / "image.elf", address, size)
        offset = address - BASE
        if _elf_function_extent(directory / "image.elf", name) != (address, size)\
                or body != image[offset:offset + size]\
                or hashlib.sha256(body).hexdigest() != digest\
                or self.session.read(owner["entry"] + offset, size) != expected[offset:offset + size]:
            raise NativeObservationError("automatic spawn typed full Control owner differs")
        selector = rt.REPO / "build/overworld_follower_selector_overlay_linked.o"
        service = symbol(selector.read_bytes(), "gOverworldQueryCodeAddonServiceEntry", 1, expected_size=24)[0]
        wild = rt.REPO / "build/overworld_wild_spawns_overlay_linked.o"
        native = native_entry_bindings(wild.read_bytes(),
            lambda address, size: self.elf_code(wild, address, size), self.session.packaged_code)
        self.query_spawn_identity = dict(owner=owner, expected=expected, service=service,
            serviceBytes=self.elf_code(selector, service, 24), ops=native["ops"], descriptorSize=ENTRY)
        for token in self.query_spawn_tokens:
            self.hooks.remove(token)
            self.tokens.remove(token)
        self.query_spawn_tokens.clear()
        for name, label, before, after, output in (
                ("NativeSpawn", "spawn-queued", self._query_spawn_before,
                 self._query_spawn_after, "spawn-queued"),
                ("NativeFinalize", "spawn-query-finalized", self._query_finalize_before,
                 self._query_finalize_after, "spawn-finalized")):
            address, size, _ = QUERY_SPAWN_OWNERS[name]
            address = owner["entry"] + address - BASE
            body = expected[address - owner["entry"]:address - owner["entry"] + size]
            token = self._query_spawn_tap(label, address, body, before, after, output)
            self.query_spawn_tokens.append(token)
            self.tokens.append(token)
        return None

    def _query_spawn_charge(self, size):
        self.query_spawn_read_bytes += size
        if self.query_spawn_read_bytes > QUERY_SPAWN_READ_CAP:
            raise NativeObservationError("automatic spawn callback read cap exceeded")

    def _query_spawn_read(self, address, size):
        if not (0x02000000 <= address < address + size <= 0x02400000
                or 0x027E0000 <= address < address + size <= 0x027E3FC0):
            raise NativeObservationError("automatic spawn callback read range differs")
        self._query_spawn_charge(size)
        data = self.session.read(address, size)
        if len(data) != size:
            raise NativeObservationError("automatic spawn callback read is short")
        return data

    def _query_spawn_public(self, address, size):
        if address & 3:
            raise NativeObservationError("automatic spawn typed buffer is not aligned")
        return self._query_spawn_read(address, size)

    def _query_spawn_subject(self, slot):
        self._query_spawn_charge(self.session.rt.ACTOR_DESCRIPTOR["state"]["actorStride"])
        return self._subject(slot)

    def _query_spawn_owner(self):
        identity = self.query_spawn_identity
        if identity is None:
            raise NativeObservationError("automatic spawn has no authenticated Query discovery")
        from tools.overworld.devtools_query_observer import BASE
        owner = identity["owner"]
        raw = self._query_spawn_public( owner["stateAddress"], 28)
        self._query_spawn_charge(20)
        world = self._world_context()
        address, size, entry, field, epoch, generation, member, phase, reserved = struct.unpack("<4I2HIB3s", raw)
        actor = self.session.rt.ACTOR_DESCRIPTOR["state"]["address"]
        # Existing stock availability reader:24 predicate +12 pointers +40
        # manager +56 exit wrapper. This is its complete worst-case read set.
        self._query_spawn_charge(132)
        lifecycle = self.session._field_actor_availability(field)
        if raw.hex() != owner["rawHex"] or phase != 1 or member != 21 or reserved != bytes(3)\
                or entry != address + 64 or field != world["fieldPointer"]\
                or (epoch, generation) != (world["fieldEpoch"], world["mapGeneration"])\
                or lifecycle.get("authenticated") is not True or lifecycle.get("reason") is not None\
                or not self._query_spawn_public( 0x023C8148, 4)[0] & 0x40\
                or self._query_spawn_public( identity["service"], 24) != identity["serviceBytes"]\
                or self.session.packaged_code(identity["service"], 24) != identity["serviceBytes"]\
                or self._query_spawn_public( actor + 12, 4)[:2] != struct.pack("<H", epoch)\
                or self._query_spawn_public( actor + 44, 4)[2:] != struct.pack("<H", generation)\
                or self._query_spawn_public( entry, identity["descriptorSize"])\
                    != identity["expected"][:identity["descriptorSize"]]:
            raise NativeObservationError("automatic spawn Query lease/service/descriptor differs")
        for address, size, _ in QUERY_SPAWN_OWNERS.values():
            offset = address - BASE
            if self._query_spawn_read(entry + offset, size) != identity["expected"][offset:offset + size]:
                raise NativeObservationError("automatic spawn Query current full native body differs")
        if self._query_spawn_public( identity["ops"][0], 72) != identity["ops"][1]:
            raise NativeObservationError("automatic spawn native Ops differs")
        return owner

    def _query_spawn_tap(self, label, address, body, before, after, output):
        self.calls[label] = dict(address=address, bodyBytes=len(body),
            entrySha256=hashlib.sha256(body).hexdigest(), entered=0, returned=0, nonmatchingEntries=0)
        def entered():
            if not spawn_cost_gate(self, output):
                return
            self.query_spawn_read_bytes = 0
            # A retired heap address may be reused. It is not a current owner.
            if self._query_spawn_read(address, 32) != body[:32]:
                return
            regs = self.session.emu.memory.register_arm9
            control = self._query_spawn_public( regs.r1 & 0xFFFFFFFF, 52)
            if control[44] not in (7, 8):
                return  # Public/follower op2 still uses its existing wrapper.
            if len(self.contexts) >= self.MAX_DEPTH:
                raise NativeObservationError("native observation nesting limit reached")
            owner = self._query_spawn_owner()
            data = before()
            if data is None:
                return
            regs = self.session.emu.memory.register_arm9
            context = dict(entry=self._clock(), setupMode="prepared" if self.session.prepared else "normal",
                           data=data, sp=regs.sp & 0xFFFFFFFF, guestEntry=self._guest_clock())
            self._query_spawn_charge(4)  # _clock's Actor frame word.
            data["entryReadBytes"] = self.query_spawn_read_bytes
            self.contexts.append(context)
            self.calls[label]["entered"] += 1
            token = None
            def returned():
                if regs.sp & 0xFFFFFFFF != context["sp"]:
                    return
                self.query_spawn_read_bytes = 0
                self.hooks.remove(token)
                self.return_tokens.remove(token)
                if not self.contexts or self.contexts[-1] is not context:
                    raise NativeObservationError("automatic spawn return lost its exact nesting owner")
                self.contexts.pop()
                if self._query_spawn_owner()["rawHex"] != owner["rawHex"]:
                    raise NativeObservationError("automatic spawn Query owner changed before return")
                context.update(returned=self._clock(), returnValue=regs.r0 & 0xFFFFFFFF,
                               guestReturn=self._guest_clock())
                self.calls[label]["returned"] += 1
                self._query_spawn_charge(4)  # _clock's Actor frame word.
                result = after(data, context)
                if result is not None:
                    result["queryCallbackReadCap"] = QUERY_SPAWN_READ_CAP
                    result["queryCallbackReadBytes"] = dict(entry=data["entryReadBytes"], returned=self.query_spawn_read_bytes)
                    self._queue(output, context, result)
            token = self.hooks.add(regs.lr, returned)
            self.return_tokens.append(token)
        return self.hooks.add(address, entered)

    def _query_queue_value(self, state, slot, *, prepared=False):
        rt = self.session.rt
        runtime = struct.unpack("<I", self._query_spawn_public(state + rt.WILD_RUNTIME_PTR_OFFSET, 4))[0]
        if runtime & 3 or not 0x02000000 <= runtime <= 0x02400000 - 2856:
            raise NativeObservationError("automatic spawn runtime pointer differs")
        value = dict(runtime=runtime, preparedPointer=runtime + 992,
            queueSlot=self._query_spawn_public( runtime + 240, 4)[0],
            terrain=self._query_spawn_public( runtime + 240, 4)[1],
            stage=self._query_spawn_public( runtime + 244, 4)[0],
            serial=struct.unpack("<I", self._query_spawn_public( runtime + 2748, 4))[0])
        if prepared:
            value["preparedHex"] = self._query_spawn_public( runtime + 992, 260).hex()
        return value

    def _query_spawn_transaction(self, *, finalizer):
        regs = self.session.emu.memory.register_arm9
        pointer = regs.r1 & 0xFFFFFFFF
        control = self._query_spawn_public( pointer, 52)
        operation, control_slot, control_terrain = control[44:47]
        if operation not in (7, 8) or (not finalizer and operation != 8):
            return None
        owner = self.query_spawn_identity["owner"]
        call_pointer = regs.r0 & 0xFFFFFFFF
        call = self._query_spawn_public( call_pointer, 32)
        world_pointer = struct.unpack_from("<I", call)[0]
        world = self._query_spawn_public( world_pointer, 84)
        command_pointer = struct.unpack_from("<I", call, 8)[0]
        command = self._query_spawn_public( command_pointer, 88)
        ops, state, field = struct.unpack_from("<3I", control, 4)
        self._query_spawn_charge(20)
        current = self._world_context()
        # NativeFinalize's real compiled ABI: base/control/state/Field in
        # r0..r3, terrain/slot/owned prepared pointer in entry stack0..8.
        words = struct.unpack("<" + ("3I" if finalizer else "2I"),
                              self._query_spawn_public(regs.sp & 0xFFFFFFFF, 12 if finalizer else 8))
        terrain, slot = words[:2]
        prepared = words[2] if finalizer else None
        query_operation = control[47]
        expected_caller = QUERY_SPAWN_CALLERS[
            ("finalizer_from_spawn" if operation == 8 else "finalizer_from_commit")
            if finalizer else ("spawn_from_refill" if query_operation == 1 else "spawn_from_single")]
        caller = (regs.lr & ~1) - owner["entry"] + 0x02080000
        if struct.unpack_from("<HH", control) != (1, 52) or control[48:] != bytes(4)\
                or slot >= 10 or slot == 7 or control_slot >= 10 or control_slot == 7 or ops != self.query_spawn_identity["ops"][0]\
                or state != current["statePointer"] or field != current["fieldPointer"]\
                or (regs.r2 & 0xFFFFFFFF, regs.r3 & 0xFFFFFFFF) != (state, field)\
                or caller != expected_caller\
                or struct.unpack_from("<HH", world) != (3, 84) or world[52] != control_slot\
                or struct.unpack_from("<II", world, 4) != (field, state)\
                or call[29:] != bytes((1, 0, 0))\
                or command[:84] != bytes(84) or struct.unpack_from("<I", command, 84)[0] != pointer\
                or struct.unpack_from("<I", control, 16)[0] != struct.unpack_from("<I", call, 4)[0]:
            raise NativeObservationError("automatic spawn typed transaction/caller differs")
        world_ops = struct.unpack_from("<I", world, 28)[0]
        if self._query_spawn_public( world_ops, 4) != struct.pack("<HH", 3, 84):
            raise NativeObservationError("automatic spawn typed World Ops differs")
        queue = self._query_queue_value(state, slot)
        parent = self.spawn_queue_contexts[-1] if self.spawn_queue_contexts else None
        if operation == 8:
            if query_operation not in (0, 1) or (query_operation == 0
                    and (control_slot != slot or control_terrain != terrain))\
                    or (query_operation == 1 and (control_slot != 0 or control_terrain != 0
                        or control[16:44] != bytes(28))):
                raise NativeObservationError("automatic spawn subtype/selected slot differs")
        elif query_operation != 0:
            raise NativeObservationError("automatic Commit subtype differs")
        if not finalizer:
            if queue["queueSlot"] != 0 or self._query_spawn_subject(slot)["status"] != "not-active":
                raise NativeObservationError("automatic Spawn input is queued or active")
            return dict(statePointer=state, fieldPointer=field, terrain=terrain, slot=slot,
                preparedPointer=queue["preparedPointer"], worldContext=current,
                nativeOwner="Query.NativeSpawn", operation=operation, queryOperation=query_operation,
                controlPointer=pointer, controlHex=control.hex(), callPointer=call_pointer,
                callHex=call.hex(), worldPointer=world_pointer, worldHex=world.hex(),
                commandPointer=command_pointer, commandHex=command.hex(), owner=owner["rawHex"],
                queueBefore=queue)
        # The current helper has one 16-query update. NativeSpawn owns that
        # remaining-update counter until its caller clears it; Commit enters
        # this leaf only for one of the named resumable finalizer stages.
        if (operation == 8 and queue["stage"] not in (0, 1))\
                or (operation == 7 and queue["stage"] not in range(0xFB, 0x100)):
            raise NativeObservationError("automatic spawn finalizer input stage differs")
        if prepared != queue["preparedPointer"] or queue["serial"] == 0\
                or (operation == 7 and (queue["queueSlot"] != slot + 1 or terrain != queue["terrain"]))\
                or self._query_spawn_subject(slot)["status"] != "not-active":
            raise NativeObservationError("Query finalizer lost its owned packet/serial/inactive actor")
        if operation == 8:
            if parent is None or any(parent[key] != value for key, value in (
                        ("statePointer", state), ("fieldPointer", field), ("slot", slot),
                        ("terrain", terrain), ("worldContext", current))):
                raise NativeObservationError("automatic Spawn has no exact inactive queue owner")
        else:
            pending = self.pending_destination_scans.get(slot)
            if pending is not None and "querySerial" in pending and pending["querySerial"] != queue["serial"]:
                raise NativeObservationError("automatic Commit finalizer changed the queued serial")
        value = dict(statePointer=state, fieldPointer=field, terrain=terrain, slot=slot,
            preparedPointer=prepared, worldContext=current, nativeOwner="Query.NativeFinalize",
            operation=operation, controlPointer=pointer, controlHex=control.hex(),
            callPointer=call_pointer, callHex=call.hex(), worldPointer=world_pointer, worldHex=world.hex(),
            commandPointer=command_pointer, commandHex=command.hex(), owner=owner["rawHex"],
            querySerial=queue["serial"], queryQueueStage=queue["stage"])
        return value

    def _query_spawn_before(self):
        value = self._query_spawn_transaction(finalizer=False)
        if value is None:
            return None
        self.spawn_queue_id += 1
        value.update(previousFinalizationId=self.finalization_id, spawnAttemptId=self.spawn_queue_id)
        self.spawn_queue_contexts.append(value)
        return value

    def _query_spawn_inputs_unchanged(self, value):
        if self._world_context() != value["worldContext"] or any(
                self._query_spawn_public(value[pointer], size).hex() != value[raw]
                for pointer, raw, size in (("controlPointer", "controlHex", 52),
                    ("callPointer", "callHex", 32), ("worldPointer", "worldHex", 84),
                    ("commandPointer", "commandHex", 88))):
            raise NativeObservationError("automatic spawn transaction input/world changed")

    def _query_spawn_after(self, value, context):
        if context["returnValue"] not in (0, 1, 2):
            raise NativeObservationError("automatic Spawn prepare result differs")
        self._query_spawn_inputs_unchanged(value)
        result = self._spawn_queue_after(value, context, query_owner_checked=True)
        result["queueAfter"] = self._query_queue_value(value["statePointer"], value["slot"],
                                                     prepared=context["returnValue"] == 1)
        return result

    def _query_finalize_before(self):
        value = self._query_spawn_transaction(finalizer=True)
        if value is None:
            return None
        self._query_spawn_charge(20)
        return self._finalize_before(value)

    def _query_finalize_after(self, value, context):
        self._query_spawn_charge(20)
        if context["returnValue"] not in (0, 1) or self._world_context() != value["worldContext"]\
                or self._query_spawn_public( value["controlPointer"], 52).hex() != value["controlHex"]\
                or self._query_spawn_public( value["callPointer"], 32).hex() != value["callHex"]\
                or self._query_spawn_public( value["worldPointer"], 84).hex() != value["worldHex"]\
                or self._query_spawn_public( value["commandPointer"], 88).hex() != value["commandHex"]:
            raise NativeObservationError("automatic spawn transaction input/world changed")
        queue = self._query_queue_value(value["statePointer"], value["slot"], prepared=True)
        if queue["serial"] != value["querySerial"]\
                or queue["preparedPointer"] != value["preparedPointer"]\
                or self._query_spawn_subject(value["slot"])["status"] != "not-active":
            raise NativeObservationError("automatic spawn owned packet/serial/finalizer changed")
        if context["returnValue"] == 1:
            # Immediate ordinary destination success preserves the exact
            # helper counter. READY Move / STARTUP finalization clears it in
            # the leaf; destination-scan and route-pending calls cannot pass.
            before_stage = value["queryQueueStage"]
            expected_stage = before_stage if value["operation"] == 8 else (
                0 if before_stage in (0xFC, 0xFE) else None)
            if expected_stage is None or queue["stage"] != expected_stage:
                raise NativeObservationError("automatic spawn finalizer success stage differs")
        self._query_spawn_charge(20 + (36 if context["returnValue"] == 1 else 0))
        result = self._finalize_after(value, context)
        result["queueAfter"] = queue
        if value["operation"] == 8:
            if not self.spawn_queue_contexts:
                raise NativeObservationError("automatic spawn finalizer lost SpawnOne")
            parent = self.spawn_queue_contexts[-1]
            if parent["spawnAttemptId"] != value["spawnAttemptId"] or parent.get("nativeEntry") is not None:
                raise NativeObservationError("automatic spawn finalizer reused its attempt")
            parent["nativeEntry"] = deepcopy(result)
        return result

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

    def _spawn_queue_after(self, value, context, *, query_owner_checked=False):
        if not self.spawn_queue_contexts or self.spawn_queue_contexts[-1] is not value:
            raise NativeObservationError("SpawnOne return lost its attempt owner")
        self.spawn_queue_contexts.pop()
        native = value.get("nativeEntry")
        if native is not None:
            if not query_owner_checked:
                self._query_spawn_owner()
            queue = self._query_queue_value(value["statePointer"], value["slot"], prepared=True)
            self._query_spawn_charge(20)
            if context["returnValue"] == 1 and (queue["queueSlot"] != value["slot"] + 1
                    or queue["terrain"] != value["terrain"]
                    or any(queue[key] != native["queueAfter"][key] for key in
                        ("runtime", "preparedPointer", "serial", "stage", "preparedHex"))):
                raise NativeObservationError("automatic queue receipt changed before SpawnOne return")
        if context["returnValue"] != 1:
            self.latest_destination_results.pop(value["spawnAttemptId"], None)
            return {**value, "queued": False}
        prior = self.finalizations.get(value["slot"])
        if prior is not None and prior["finalizationId"] > value["previousFinalizationId"]\
                and all(prior[key] == value[key] for key in (
                    "statePointer", "fieldPointer", "terrain", "slot", "worldContext"))\
                and self._world_context() == value["worldContext"]:
            # Only an authenticated successful enqueue can cross one completed
            # queue. The next boundary expires it even when creation is cancelled.
            self.queued_finalizations[value["slot"]] = prior["finalizationId"]
            self.pending_destination_scans.pop(value["slot"], None)
            self.latest_destination_results.pop(value["spawnAttemptId"], None)
            return {**value, "queued": True, "pendingDestination": False,
                    "finalizationId": prior["finalizationId"]}
        final = self.latest_finalization_results.get(value["slot"])
        if native is not None and final is not None and final["returnValue"] == 0:
            if native["operation"] != 8 or native["returnValue"] != 0\
                    or native["finalizationId"] != final["finalizationId"]\
                    or native["spawnAttemptId"] != value["spawnAttemptId"]\
                    or queue["stage"] not in range(0xFB, 0x100)\
                    or self._world_context() != value["worldContext"]\
                    or self._query_spawn_subject(value["slot"])["status"] != "not-active":
                raise NativeObservationError("automatic queue receipt changed before SpawnOne return")
            self.pending_destination_scans[value["slot"]] = dict(
                {key: deepcopy(final[key]) for key in (
                    "statePointer", "fieldPointer", "terrain", "slot", "preparedPointer", "worldContext")},
                spawnAttemptId=value["spawnAttemptId"], querySerial=queue["serial"])
            self.latest_destination_results.pop(value["spawnAttemptId"], None)
            return {**value, "queued": True, "pendingDestination": queue["stage"] in (0xFB, 0xFF),
                    "pendingEntry": queue["stage"] in (0xFC, 0xFD, 0xFE),
                    "finalizationId": final["finalizationId"]}
        destination = self.latest_destination_results.get(value["spawnAttemptId"])
        if final is None or destination is None\
                or final.get("finalizationId", 0) <= value["previousFinalizationId"]\
                or final.get("returnValue") != 0\
                or destination.get("finalizationId") != final.get("finalizationId")\
                or destination.get("candidateQueryCount") != 0\
                or destination.get("spawnAttemptId") != value["spawnAttemptId"]\
                or any(final.get(key) != value[key] for key in (
                    "statePointer", "fieldPointer", "terrain", "slot", "worldContext"))\
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

    def _finalize_before(self, value=None):
        value = self._prepared_call() if value is None else value
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
            if old["preparedPointer"] == value["preparedPointer"]\
                    or old["worldContext"] != value["worldContext"]:
                del self.finalizations[slot]
        pair = {"status": "missing"}
        if prior is not None:
            pair = {"status": "matched", "receipt": prior}
            if any(prior[key] != value[key] for key in (
                    "statePointer", "fieldPointer", "slot", "terrain", "preparedPointer", "worldContext"))\
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
            else "OverworldWildSpawns_StartPreparedCustomJumpCommandWithArc",
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
        result = public_bytes(self.session, value["resultAddress"], 216)
        if not value["controlledCall"]:
            # Discovery is one bounded private receipt. A later prepared probe
            # must authenticate current code/blob and recheck this field owner.
            # Its own controlled calls cannot replace the natural discovery.
            self.resolver_discovery = {key: value[key] for key in (
                "blobAddress", "blobSize", "fieldPointer", "heapGeneration", "requestHex")}
            self.resolver_discovery.update(status=0,
                entryNativeCycle=context["entry"]["nativeCycle"],
                returnNativeCycle=context["returned"]["nativeCycle"])
        fingerprint = int.from_bytes(result[192:196], "little")
        receipt = {"requestHex": value["requestHex"], "resultHex": result.hex(), "resolved": True,
                   "fingerprint": fingerprint, "sourceSha256": self.source_hash,
                   "lanes": [result[n:n + 80].hex() for n in (0, 80)],
                   "appliedOverrides": int.from_bytes(result[188:192], "little")}
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
                    or policy_size != 36 or policy_offset < 88
                    or policy_offset + policy_size > stride
                    or address & 3 or not 0x02000000 <= address < address + size <= 0x02400000
                    or offset + stride * capacity > size):
                raise ValueError("invalid span")
            return address + offset + slot * stride + policy_offset
        except (KeyError, TypeError, ValueError) as error:
            raise NativeObservationError("public Walk COMMIT policy layout differs") from error

    def _commit_policy(self, slot):
        raw = public_bytes(self.session, self._commit_policy_address(slot), 36)
        names = ("direction", "counter", "speed", "base", "spotState", "skid", "turn", "resume",
                 "chain", "ticks", "action", "variance", "buffered", "stop", "pending", "pendingSkid", "streamState",
                 "linearElapsed", "linearCarry", "linearMode", "linearCapFrames")
        return raw.hex(), dict(zip(names, (raw[index] for index in (*range(8), *range(16, 25), *range(32, 36)))))

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
            value["laneHex"] = public_bytes(self.session, int.from_bytes(call[4:8], "little"), 80).hex()
            self.policy_contexts.append(value)
        if call[9] in (1, 3):
            subject = value["publicSubject"]
            if (subject.get("status") != "observed-public-subject"
                    or subject.get("handle", {}).get("slot") != call[8]
                    or any(type(subject.get(key)) is not int or subject[key] <= 0
                           for key in ("authorityGeneration", "engineAnchorGeneration", "presentationGeneration"))
                    or any(type(subject.get("handle", {}).get(key)) is not int
                           for key in ("generation", "fieldEpoch", "mapGeneration", "encounterGeneration"))):
                raise NativeObservationError("public Walk COMMIT subject is absent or differs")
            value["laneHex"] = public_bytes(self.session, int.from_bytes(call[4:8], "little"), 80).hex()
            control = getattr(self.session, "walk_policy_control", None)
            read = lambda: self._commit_policy(call[8])
            value["policyBeforeHex"], value["policyBefore"] = (
                control.capture(self, call[8], read)
                if call[9] == 3 and control is not None else read())
        return value

    def _policy_after(self, value, context):
        if value in self.policy_contexts:
            self.policy_contexts.remove(value)
        response = public_bytes(self.session, value["address"], 28)
        if response[:4] != b"\x01\x00\x1c\x00" or response[8:10] != bytes((value["slot"], value["operation"])):
            raise NativeObservationError("public Walk policy response identity differs")
        after = self._subject(value["slot"])
        if value["operation"] in (1, 3):
            identity = ("status", "handle", "species", "form", "level", "subjectIdentity", "role",
                        "authorityGeneration", "engineAnchorGeneration", "presentationGeneration")
            if any(value["publicSubject"].get(key) != after.get(key) for key in identity):
                raise NativeObservationError("public Walk COMMIT subject identity differs")
            request = bytes.fromhex(value["requestHex"])
            if (response[4:8] != request[4:8] or public_bytes(self.session,
                    int.from_bytes(request[4:8], "little"), 80).hex() != value["laneHex"]):
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

    def _playful_current(self, slot, state, object_pointer=None):
        rt = self.session.rt
        if state != rt.WILD_STATE or not 0 <= slot < rt.ACTOR_DESCRIPTOR["capacities"]["actors"]:
            return None
        subject = self._subject(slot)
        if (subject.get("status") != "observed-public-subject"
                or subject.get("species") != 35 or subject.get("form") != 0
                or subject.get("role") != "WILD"):
            return None
        spawn = rt.wild_spawn(self.session.emu, slot)
        if (spawn.get("active") != 1 or spawn.get("species") != 35
                or spawn.get("form") != 0 or not spawn.get("object")
                or (object_pointer is not None and spawn["object"] != object_pointer)):
            return None
        return subject

    def _playful_sequence_before(self):
        regs = self.session.emu.memory.register_arm9
        if regs.r3 != 1:  # Authored HOP_IN_PLACE, not a different chain action.
            return None
        subject = self._playful_current(regs.r1, regs.r0)
        if subject is None:
            return None
        value = {"slot": regs.r1, "publicSubject": subject, "rngReturns": []}
        self.playful_contexts.append(value)
        return value

    def _playful_sequence_after(self, value, context):
        if not self.playful_contexts or self.playful_contexts[-1] is not value:
            raise NativeObservationError("Playful sequence RNG owner changed")
        self.playful_contexts.pop()
        after = self._playful_current(value["slot"], self.session.rt.WILD_STATE)
        if after != value["publicSubject"]:
            raise NativeObservationError("Playful sequence changed its full current owner")
        return {**value, "publicSubjectAfter": after}

    def _playful_step_before(self):
        regs = self.session.emu.memory.register_arm9
        subject = self._playful_current(regs.r1, regs.r0, regs.r2)
        if subject is None:
            return None
        self.playful_step_id += 1
        value = {"stepId": self.playful_step_id, "slot": regs.r1,
                 "objectPointer": regs.r2, "publicSubject": subject,
                 "heartCalls": 0, "cryCalls": 0}
        self.playful_step_contexts.append(value)
        return value

    def _playful_step_after(self, value, context):
        if not self.playful_step_contexts or self.playful_step_contexts[-1] is not value:
            raise NativeObservationError("Playful stock command owner changed")
        self.playful_step_contexts.pop()
        after = self._playful_current(value["slot"], self.session.rt.WILD_STATE, value["objectPointer"])
        if after != value["publicSubject"]:
            raise NativeObservationError("Playful stock command changed its full current owner")
        pose = self.session.rt.object_state(self.session.emu, value["objectPointer"])
        command = pose["movement_cmd"]
        if not 0x30 <= command <= 0x33 or context["returnValue"] != 1:
            if value["heartCalls"] or value["cryCalls"]:
                raise NativeObservationError("Playful effect occurred outside accepted JUMP start")
            if command == 0x49 and context["returnValue"] == 1:
                # Stock PREP can finish before this completed update is sampled.
                # Retain the real accepted call through the existing step tap.
                return {**value, "publicSubjectAfter": after, "command": command,
                        "objectPose": {key: pose[key] for key in
                                       ("pos_x", "pos_y", "pos_z", "face_y", "unk88_y")}}
            return None
        return {**value, "publicSubjectAfter": after, "command": command}

    def _playful_cry_before(self):
        regs = self.session.emu.memory.register_arm9
        step = self.playful_step_contexts[-1]
        if (regs.r0 & 0xFFFF, regs.r1 & 0xFF) != (35, 0):
            raise NativeObservationError("Playful JUMP used another Pokemon cry")
        step["cryCalls"] += 1
        return {"stepId": step["stepId"], "publicSubject": step["publicSubject"],
                "species": regs.r0 & 0xFFFF, "form": regs.r1 & 0xFF,
                "caller": regs.lr & ~1}

    def _playful_heart_before(self):
        regs = self.session.emu.memory.register_arm9
        step = self.playful_step_contexts[-1]
        if regs.r0 != step["objectPointer"] or regs.r1 != 0:
            raise NativeObservationError("Playful JUMP heart object or effect ID differs")
        step["heartCalls"] += 1
        return {"stepId": step["stepId"], "publicSubject": step["publicSubject"],
                "objectPointer": regs.r0, "bubbleId": regs.r1,
                "caller": regs.lr & ~1}

    def _playful_effect_after(self, value, context):
        return value

    def _playful_heart_after(self, value, context):
        from tools.overworld.devtools_records import stock_bubble_admitted
        pointer = context["returnValue"]
        if stock_bubble_admitted(pointer):
            self.playful_hearts[pointer] = deepcopy(value)
            self.playful_hearts.move_to_end(pointer)
            while len(self.playful_hearts) > self.MAX_PROFILES:
                self.playful_hearts.popitem(last=False)
        return value

    def _playful_heart_draw_before(self):
        regs = self.session.emu.memory.register_arm9
        original = self.playful_hearts[regs.r0]
        # Retail draw data: hidden flag +0x10, current object +0x38,
        # rendered model +0x3C. Only the actual same-owner visible draw earns credit.
        raw = public_bytes(self.session, regs.r1, 64)
        hidden, object_pointer, model = (struct.unpack_from("<I", raw, offset)[0]
                                          for offset in (0x10, 0x38, 0x3C))
        current = self._playful_current(original["publicSubject"]["slot"],
                                       self.session.rt.WILD_STATE, object_pointer)
        identity = ("handle", "species", "form", "role", "subjectIdentity",
                    "authorityGeneration", "engineAnchorGeneration", "presentationGeneration")
        if (current is None or object_pointer != original["objectPointer"]
                or any(current[key] != original["publicSubject"][key] for key in identity)):
            return None
        return {"effectPointer": regs.r0, "objectPointer": object_pointer,
                "publicSubject": current, "bubbleId": original["bubbleId"],
                "hidden": hidden, "modelPointer": model,
                "visible": hidden != 1 and 0x02000000 <= model < 0x02400000}

    def _safety_bubble_current(self, expected_object):
        from tools.overworld.devtools_runtime import actor_identity_checks
        rt, emu = self.session.rt, self.session.emu
        matches = []
        # Keep the existing Cleffa follower scope; add only the reported Wild
        # Igglybuff. This observes the same stock call without changing it.
        for slot in range(min(8, rt.ACTOR_DESCRIPTOR["capacities"]["actors"])):
            actor = rt.actor_state(emu, slot)
            eligible = ((slot == 7 and actor.get("role") == "FOLLOWER"
                         and actor.get("species") == 173)
                        or (slot < 7 and actor.get("role") == "WILD"
                            and actor.get("species") == 174))
            if actor.get("active") is not True or not eligible or actor.get("form") != 0:
                continue
            source = rt.wild_spawn(emu, slot)
            if source.get("object") != expected_object:
                continue
            engine = rt.live_wild_object_identity(emu, slot)
            checks = actor_identity_checks(actor, source, engine, self._world_context(), slot)
            checks["form"] = source.get("form") == actor["form"]
            checks["uniqueObject"] = (engine.get("id_lookup", {}).get("status") == "complete"
                                      and engine["id_lookup"].get("eligible_count") == 1
                                      and engine["id_lookup"].get("pointer_matches") is True)
            if not all(checks.values()):
                raise NativeObservationError("safety bubble baby identity differs: " + ", ".join(
                    name for name, passed in checks.items() if not passed))
            matches.append((self._subject(slot), source, engine))
        if len(matches) > 1:
            raise NativeObservationError("safety bubble object has multiple current babies")
        return matches[0] if matches else None

    def _safety_bubble_before(self):
        regs = self.session.emu.memory.register_arm9
        current = self._safety_bubble_current(regs.r0)
        if current is None:
            return None
        subject, source, engine = current
        return {"publicSubject": subject, "objectPointer": regs.r0,
                "sourceObjectPointer": source["object"],
                "engineObjectPointer": engine["pointer"],
                "bubbleId": regs.r1 & 0xFFFFFFFF, "caller": regs.lr & ~1,
                "worldContext": self._world_context()}

    def _safety_bubble_after(self, value, context):
        current = self._safety_bubble_current(value["objectPointer"])
        if current is None or self._world_context() != value["worldContext"]\
                or current[0] != value["publicSubject"]\
                or current[1]["object"] != value["objectPointer"]\
                or current[2]["pointer"] != value["objectPointer"]:
            raise NativeObservationError("safety bubble lost its current baby or object")
        return {**value, "publicSubjectAfter": current[0]}

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

    def _pool_fly_terrain_snapshot(self, snapshot):
        """Two exact loaded-cell reads for a normal finalized Ledyba POOL flight.

        Reuse the existing native spawn receipts and coherent sampler. No
        native call/hook, synthetic height, full terrain scan or game mutation.
        """
        flights = getattr(self, "pool_fly_terrain", None)
        if flights is None:
            flights = self.pool_fly_terrain = {}
        for event in self.ready:
            data = event.get("data", {})
            if event.get("frame") != snapshot.get("frame") or data.get("observation") != "spawn-prepared"\
                    or data.get("returnValue") != 1 or data.get("setupMode") != "normal"\
                    or data.get("preparedEncounter", {}).get("species") != 165\
                    or data.get("startup", {}).get("locomotion") != 9:
                continue
            final = data.get("finalization", {}).get("receipt", {})
            profiles = final.get("resolverReceipts", [])
            if data.get("finalization", {}).get("status") != "matched" or final.get("returnValue") != 1\
                    or final.get("pairEligible") is not True or not profiles:
                raise NativeObservationError("Pool Fly In lacks its exact successful finalizer")
            raw = bytes.fromhex(profiles[-1].get("resultHex", ""))
            if len(raw) != 216:
                raise NativeObservationError("Pool Fly In final profile extent differs")
            # Non-Pool/explicit placements have their own proof. Do not add
            # physical reads to them or silently classify them as this case.
            if raw[17] != 0 or int.from_bytes(raw[54:56], "little") != 0:
                continue
            slot = data.get("slot")
            subject = data.get("publicSubject", {})
            if type(slot) is not int or not 0 <= slot < 6 or subject.get("role") != "WILD"\
                    or subject.get("species") != 165 or subject.get("handle", {}).get("slot") != slot\
                    or data.get("position") != data["startup"].get("target")\
                    or final.get("preparedPointer") != data.get("preparedPointer")\
                    or final.get("startupHex") != data.get("startupHex")\
                    or final.get("preparedPrefixHex") != data.get("preparedPrefixHex")\
                    or final.get("preparedEncounter") != data.get("preparedEncounter")\
                    or final.get("worldContext") != data.get("worldContext"):
                raise NativeObservationError("Pool Fly In full spawn/finalizer binding differs")
            jumps = data.get("jumpReceipts")
            if not isinstance(jumps, list) or len(jumps) != 1 or jumps[0].get("returnValue") != 1:
                raise NativeObservationError("Pool Fly In native START is missing")
            if slot in flights:
                raise NativeObservationError("Pool Fly In admission duplicates a still-bound flight")
            flights[slot] = {"subject": deepcopy(subject), "source": deepcopy(jumps[0]["sourceIdentity"]),
                "world": deepcopy(data["worldContext"]), "target": list(data["position"]),
                "commit": subject["commitSequence"], "admission": True}
        rows = []
        for slot, flight in list(flights.items()):
            world, subject = flight["world"], flight["subject"]
            if snapshot.get("prepared") is not False or snapshot.get("observationBoundary") != "main-task-queue-completion"\
                    or any(snapshot.get("context", {}).get(k) != world.get(k) for k in
                           ("mapId", "fieldEpoch", "mapGeneration")):
                del flights[slot]
                continue
            actors = [a for a in snapshot.get("actors", []) if a.get("handle") == subject.get("handle")]
            if len(actors) != 1:
                del flights[slot]
                continue
            actor = actors[0]
            if actor.get("sourceIdentity") != flight["source"] or actor.get("identityVerified") is not True\
                    or any(actor.get(k) != subject.get(k) for k in
                           ("species", "role", "subjectIdentity", "authorityGeneration", "engineAnchorGeneration", "presentationGeneration"))\
                    or self._world_context() != world:
                raise NativeObservationError("Pool Fly In current actor/Field binding differs")
            if flight["admission"] and (actor.get("motionKind") != "FLY_IN"
                    or actor.get("motionPhase") != "MOVING" or actor.get("motionDuration") != 144
                    or actor.get("motionElapsed") not in (0, 1)
                    or actor.get("commitSequence") != flight["commit"]):
                raise NativeObservationError("Pool Fly In admission motion differs")
            terminal = actor.get("commitSequence") == ((flight["commit"] + 1) & 0xFFFFFFFF)\
                and (actor.get("motionPhase") == "IDLE" and actor.get("motionElapsed") == 144
                     and [actor.get("logical", {}).get(k) for k in ("x", "y")] == flight["target"]
                     or actor.get("motionPhase") == "MOVING" and actor.get("motionElapsed") == 0
                     and [actor.get("origin", {}).get(k) for k in ("x", "y")] == flight["target"])
            if not flight["admission"] and not terminal:
                continue
            target = flight["target"]
            cell = self.session.rt.loaded_terrain_cell(self.session.emu, *target)
            if cell is not None:
                if [cell.get("x"), cell.get("y")] != target\
                        or cell.get("provenance", {}).get("fieldPointer") != world["fieldPointer"]:
                    raise NativeObservationError("Pool Fly In loaded cell belongs to another target/Field")
                cell = deepcopy(cell)
                cell["surface"] = self.session.rt.loaded_surface_cell(self.session.emu, *target, cell)
            if self._world_context() != world:
                raise NativeObservationError("Pool Fly In Field changed during its loaded cell read")
            rows.append({"status": "observed" if cell is not None else "unknown",
                "stage": "admission" if flight["admission"] else "terminal",
                "subject": deepcopy(subject), "worldContext": deepcopy(world), "target": list(target), "cell": cell})
            flight["admission"] = False
            if terminal:
                del flights[slot]
        if rows:
            snapshot["poolFlyTerrain"] = rows

    def completed_snapshot(self, snapshot):
        """Retain the one controlled natural Appear Hop across boot frames."""
        query = getattr(self, "query", None)
        if query is not None:
            query.completed_snapshot(snapshot)
        self._pool_fly_terrain_snapshot(snapshot)
        appearance = getattr(self, "appearance", None)
        if appearance is not None:
            appearance.sample(snapshot)
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
        if type(command) is not int or type(state) is not int\
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
        if self.null_model_getter is not None:
            value['nullModelDataGetter'] = deepcopy(self.null_model_getter)
        if self.null_model_visibility is not None:
            value['nullModelVisibility'] = deepcopy(self.null_model_visibility)
        if self.null_model_position is not None:
            value['nullModelPosition'] = deepcopy(self.null_model_position)
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
        if hasattr(self, "fly_landing_cost"):
            self.fly_landing_cost.frame = None
            self.fly_landing_cost.bubbles.clear()
        self.spawn_contexts.clear()
        self.spawn_queue_contexts.clear()
        self.query_spawn_identity = None
        self.query_spawn_tokens.clear()
        self.destination_contexts.clear()
        self.latest_destination_results.clear()
        self.pending_destination_scans.clear()
        self.policy_contexts.clear()
        self.playful_contexts.clear()
        self.playful_step_contexts.clear()
        self.finalization_contexts.clear()
        self.finalizations.clear()
        self.latest_finalization_results.clear()
        self.queued_finalizations.clear()
        self.latest_finalizations.clear()
        self.pool_fly_terrain.clear()
        self.reposition_contexts.clear()
        self.reposition_call_sites.clear()
        self.spawn_height_trace = None
