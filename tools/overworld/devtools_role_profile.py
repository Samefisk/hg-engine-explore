"""Temporary read-only follower getter / mounted Owner transfer observations.

Install creates no hooks. The explicit prepared lifecycle capture window owns
two entry taps and retires empty dispatchers on exit, not on every native call.
Receipts prove observed bytes/ownership only; the controller compares Workshop.
Explicit capture(control=True) changes/restores one owned Owner byte without
guest execution and tests the same snapshot checker. Default capture is read-only.
"""
from contextlib import contextmanager
from copy import deepcopy
import struct
import sys

from tools.overworld.devtools_observer import NativeObservationError, public_bytes

FOLLOWER_SLOT = 7
PROFILE_BYTES, PRIMITIVE_BYTES = 144, 8
BINDING_BYTES, SNAPSHOT_BYTES, SNAPSHOT_OFFSET = 16, 96, 8
MAX_RECEIPTS = 128
MAX_CAPTURES = 16


class RoleProfileControlFailure(NativeObservationError):
    code = "role-profile-control-failed"
    fatal = True


def require(ok, reason):
    if not ok:
        raise NativeObservationError("role profile: " + reason)


def install_role_profiles(observer, linked):
    return RoleProfileObserver(observer, linked)


class RoleProfileObserver:
    def __init__(self, observer, linked):
        self.observer, self.session, self.linked = observer, observer.session, linked
        self.active = False
        self.count = 0
        self.capture_count = 0
        self.owned_data = []
        self.owned_entries = []
        self.owned_returns = []
        self.control = False
        self.control_done = False

    def _install_tap(self, *args, **kwargs):
        observer = self.observer
        start = len(observer.tokens)
        try:
            self.linked(*args, **kwargs)
        finally:
            # Installation is synchronous. Capture only this call's entries,
            # including a partially successful install, not later window taps.
            self.owned_entries.extend(observer.tokens[start:])
        for token in list(observer.tokens[start:]):
            address, callback = token
            # _tap adds its return listener synchronously during entry. Track
            # that exact listener, not other observers' later pending returns.
            def tracked(callback=callback):
                before = list(observer.return_tokens)
                try:
                    return callback()
                finally:
                    self.owned_returns.extend(t for t in observer.return_tokens if t not in before)
            observer.hooks.remove(token)
            replacement = observer.hooks.add(address, tracked)
            observer.tokens[observer.tokens.index(token)] = replacement
            self.owned_entries[self.owned_entries.index(token)] = replacement

    def _track(self, data):
        self.owned_data.append(data)
        return data

    @contextmanager
    def capture(self, *, control=False):
        require(type(control) is bool, "control option must be boolean")
        require(not self.active and self.session.prepared, "capture requires one prepared lifecycle")
        require(self.capture_count < MAX_CAPTURES, "per-session capture limit exceeded")
        self.capture_count += 1
        observer, rt = self.observer, self.session.rt
        self.owned_data, self.owned_entries, self.owned_returns = [], [], []
        self.active, self.count = True, 0
        self.control, self.control_done = control, False
        try:
            wild = rt.REPO / "build/overworld_wild_spawns_overlay_linked.o"
            mount = rt.REPO / "build/overworld_mount_overlay_linked.o"
            self.mount_state = rt.linked_symbol(rt.MOUNT_SYMBOLS, "sOverworldMountState")
            self._install_tap("role-profile-getter", wild, rt.WILD_SYMBOLS,
                "OverworldWildSpawns_GetBehaviorProfileAndPrimitivesForSlot",
                self.getter_before, self.getter_after, scope=lambda: self.active)
            self._install_tap("role-profile-mount", mount, rt.MOUNT_SYMBOLS,
                "OverworldMount_Begin", self.mount_before, self.mount_after, scope=lambda: self.active)
            yield self
        finally:
            original = sys.exc_info()[1]
            self.active = False
            self.control = False
            pending = [c for c in observer.contexts
                       if any(c.get("data") is data for data in self.owned_data)]
            owned = self.owned_entries + self.owned_returns
            errors = []
            if pending:
                errors.append(NativeObservationError("pending owned role-profile return at capture close"))
                observer.contexts[:] = [c for c in observer.contexts if not any(c is p for p in pending)]
            for token in owned:
                try:
                    observer.hooks.remove(token)
                    for collection in (observer.tokens, observer.return_tokens):
                        if token in collection:
                            collection.remove(token)
                    if self.session.emu is not None:
                        observer.hooks.retire_empty(token[0])
                except Exception as error:
                    errors.append(error)
            if errors:
                if original is not None:
                    original.role_profile_cleanup_errors = [str(e) for e in errors]
                else:
                    raise NativeObservationError("role profile hook cleanup failed: " + str(errors[0])) from errors[0]
            self.owned_data, self.owned_entries, self.owned_returns = [], [], []

    def _owner(self):
        from tools.overworld.devtools_runtime import actor_identity_checks
        s, rt = self.session, self.session.rt
        actor = rt.actor_state(s.emu, FOLLOWER_SLOT)
        if actor.get("active") is not True or not actor.get("presentationAttached"):
            return None  # A pre-attach setup getter is not an owned actor receipt.
        state = rt.ACTOR_DESCRIPTOR["state"]
        context = dict(mapId=rt.field_map_id(s.emu),
            fieldEpoch=rt.unsigned(s.emu,state["address"]+state["offsets"]["fieldEpoch"],2),
            mapGeneration=rt.unsigned(s.emu,state["address"]+state["offsets"]["mapGeneration"],2))
        source = rt.wild_spawn(s.emu, FOLLOWER_SLOT)
        engine = rt.live_wild_object_identity(s.emu, FOLLOWER_SLOT)
        checks = actor_identity_checks(actor,source,engine,context,FOLLOWER_SLOT)
        require(all(checks.values()) and actor["form"] == source["form"]
                and actor["level"] == source["level"] and engine["pointer"] == source["object"],
                "native/public subject binding differs")
        return dict(fieldPointer=s.field_pointer(), heapGeneration=s.native_heap_generation,
            context=context, publicSubject=self.observer._subject(FOLLOWER_SLOT), sourceIdentity=source,
            engineIdentity=engine, identityChecks=checks)

    def _same(self, before):
        after = self._owner()
        require(after is not None, "subject vanished before return")
        for key in ("fieldPointer", "heapGeneration", "context", "sourceIdentity"):
            require(before[key] == after[key], "subject owner changed: " + key)
        for key in ("handle", "species", "form", "level", "subjectIdentity", "role",
                    "authorityGeneration", "engineAnchorGeneration", "presentationGeneration"):
            require(before["publicSubject"][key] == after["publicSubject"][key], "public subject changed: " + key)
        return after

    def _count(self):
        self.count += 1
        require(self.count <= MAX_RECEIPTS, "prepared receipt limit exceeded")

    def getter_before(self):
        regs = self.session.emu.memory.register_arm9
        if regs.r1 != FOLLOWER_SLOT:
            return None
        require(regs.r0 == self.session.rt.WILD_STATE, "getter state pointer differs")
        owner = self._owner()
        if owner is None:
            return None
        # The native getter permits either output to be NULL. Such calls do
        # not observe a full transfer, but non-NULL buffers must still be valid.
        if regs.r2 != 0:
            public_bytes(self.session,regs.r2,PROFILE_BYTES)
        if regs.r3 != 0:
            public_bytes(self.session,regs.r3,PRIMITIVE_BYTES)
        if regs.r2 == 0 or regs.r3 == 0:
            return None
        self._count()
        return self._track(dict(owner=owner,profilePointer=regs.r2,primitivesPointer=regs.r3,
                    resolverSequence=self.observer.sequence))

    def getter_after(self, value, context):
        after = self._same(value["owner"])
        return dict(ownerBefore=value["owner"],ownerAfter=after,
            profileHex=public_bytes(self.session,value["profilePointer"],PROFILE_BYTES).hex(),
            primitivesHex=public_bytes(self.session,value["primitivesPointer"],PRIMITIVE_BYTES).hex(),
            profilePointer=value["profilePointer"],primitivesPointer=value["primitivesPointer"],
            nestedResolverSequenceStart=value["resolverSequence"],
            nestedResolverSequenceEnd=self.observer.sequence,
            nativeReturnKind="void",returnValue=None,
            scope="prepared native follower slot getter; cache hit or resolution, no inferred cache provenance")

    def mount_before(self):
        self._count()
        s = self.session
        regs = s.emu.memory.register_arm9
        owner = self._owner()
        require(owner is not None and owner["publicSubject"]["role"] == "FOLLOWER"
                and regs.r0 == owner["fieldPointer"], "mount has no current follower owner")
        binding = public_bytes(s,regs.r1,BINDING_BYTES)
        pid,species,map_id,map_gen,encounter,form,level,slot,behavior = struct.unpack("<IHHHHBBBB",binding)
        actor = owner["publicSubject"]
        require((pid,species,form,level,map_id,map_gen,encounter) ==
                (actor["subjectIdentity"],actor["species"],actor["form"],actor["level"],
                 owner["context"]["mapId"],actor["handle"]["mapGeneration"],actor["handle"]["encounterGeneration"])
                and 0 <= slot < 6, "mount binding differs from follower")
        surface = struct.unpack("<I",public_bytes(s,regs.sp,4))[0]
        # The public catalog consists of u16-based packed directory/instance
        # data. Its alignment is two, not the pointer/stack alignment of four.
        require(surface % 2 == 0 and 0x02000000 <= surface <= 0x02400000-4,
                "surface catalog is outside halfword-aligned public RAM")
        require(len(s.read(surface,4)) == 4, "surface catalog read is incomplete")
        return self._track(dict(owner=owner,bindingHex=binding.hex(),partySlot=slot,
            profileHex=public_bytes(s,regs.r2,PROFILE_BYTES).hex(),
            primitivesHex=public_bytes(s,regs.r3,PRIMITIVE_BYTES).hex(),surfacePointer=surface,
            profilePointer=regs.r2,primitivesPointer=regs.r3))

    def mount_after(self, value, context):
        owner = self._same(value["owner"])
        require(context["returnValue"] == 1, "mount Begin rejected")
        data = public_bytes(self.session,self.mount_state,SNAPSHOT_OFFSET+SNAPSHOT_BYTES)
        snapshot,generation,phase = self._check_mount_snapshot(value,owner,data)
        control = self._calibrate(value,owner,data) if self.control else None
        return dict(**value,ownerAfter=owner,ownerHex=snapshot[:72].hex(),sessionGeneration=generation,
                    mountPhase=phase,scope="prepared mount Begin input-to-Owner transfer only",
                    **({"readerControl":control} if control is not None else {}))

    def _check_mount_snapshot(self, value, owner, data):
        field,surface = struct.unpack_from("<II",data)
        snapshot = data[SNAPSHOT_OFFSET:]
        generation,phase,cancel,motion,reserved = struct.unpack_from("<IBBBB",snapshot,88)
        require(field == owner["fieldPointer"] and surface == value["surfacePointer"]
                and snapshot[:72].hex() == value["profileHex"][:144]
                and snapshot[72:88].hex() == value["bindingHex"]
                and generation > 0 and (phase,cancel,motion,reserved) == (1,0,0,0),
                "mounted Owner snapshot differs from Begin inputs")
        return snapshot,generation,phase

    def _calibrate(self, value, owner, clean):
        require(self.active and not self.control_done, "reader control is single-use per capture")
        self.control_done = True
        s = self.session
        address = self.mount_state+SNAPSHOT_OFFSET
        before = clean[SNAPSHOT_OFFSET:SNAPSHOT_OFFSET+1]
        fault = bytes([before[0]^1])
        clock = lambda: {"frame":s.completed_frames,"nativeCycle":s.rt.EXECUTED_FRAME_COUNT}
        start = clock()
        rejected = None
        bad = None
        original = None
        try:
            s.rt.actor_memory_write(s.emu,address,fault)
            bad = public_bytes(s,self.mount_state,SNAPSHOT_OFFSET+SNAPSHOT_BYTES)
            expected = bytearray(clean);expected[SNAPSHOT_OFFSET]^=1
            require(bad == bytes(expected), "control changed more than the owned Owner byte")
            try:
                self._check_mount_snapshot(value,self._same(value["owner"]),bad)
            except NativeObservationError as error:
                require(str(error) == "role profile: mounted Owner snapshot differs from Begin inputs",
                        "control rejected for unrelated cause")
                rejected = str(error)
            require(rejected is not None, "normal reader accepted the changed Owner byte")
        except Exception as error:
            original = error
            raise
        finally:
            # No guest call, cycle or instruction is executed between write and
            # restoration. Restore even if the changed read/identity check fails.
            try:
                s.rt.actor_memory_write(s.emu,address,before)
                restored = public_bytes(s,self.mount_state,SNAPSHOT_OFFSET+SNAPSHOT_BYTES)
                require(restored == clean, "reader control restoration differs")
                self._check_mount_snapshot(value,self._same(value["owner"]),restored)
                require(clock() == start, "guest advanced during reader control")
            except Exception as error:
                failure = RoleProfileControlFailure("reader control restoration failed: "+str(error))
                if original is not None:
                    original.fatal = True
                    original.role_profile_restoration_error = str(failure)
                    raise original from error
                raise failure from error
        return {"acceptedProof":False,"scope":"native Owner reader calibration only; prepared observer-control mutation",
            "address":address,"beforeHex":before.hex(),"faultHex":fault.hex(),"restoredHex":before.hex(),
            "beforeSnapshotHex":clean.hex(),"faultSnapshotHex":bad.hex(),"restoredSnapshotHex":restored.hex(),
            "rejected":True,"reason":rejected,"writes":2,"beforeClock":start,"afterClock":clock(),
            "guestAdvanced":False}
