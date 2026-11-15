"""Bounded, read-only Heap_Free telemetry for one prepared ScriptWarp."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import struct

from tools.overworld.devtools_runtime import DevtoolsFailure, STOCK_CALLBACKS, require


HEAP_INFO = 0x021D1584
MAIN_RAM_START = 0x02000000
MAIN_RAM_END = 0x02400000
MAX_EVENTS = 64


def _inside_main_ram(address, size):
    return (type(address) is int and type(size) is int and size >= 0
            and MAIN_RAM_START <= address <= address + size <= MAIN_RAM_END)


class ScriptWarpHeapFreeObserver:
    """Read the stock Heap_Free inputs while one owned ScriptWarp runs.

    The observer changes no guest register or memory. It keeps a bounded tail
    so a long field teardown cannot grow the host receipt without limit.
    """

    def __init__(self, session, constructor):
        self.session = session
        tasks = constructor.get("tasks", []) if isinstance(constructor, dict) else []
        require(len(tasks) > 0, "ScriptWarp constructor has no owned task", "transition-constructor-mismatch")
        task = tasks[0]
        self.task_pointer = task.get("pointer")
        self.environment = task.get("environment")
        self.callback = STOCK_CALLBACKS["script_warp_task"] | 1
        require(task.get("function") == self.callback,
                "ScriptWarp constructor callback differs", "transition-constructor-mismatch")
        require(_inside_main_ram(self.task_pointer, 32) and self.task_pointer % 4 == 0,
                "ScriptWarp task pointer is invalid", "transition-constructor-mismatch")
        require(_inside_main_ram(self.environment, 24) and self.environment % 4 == 0,
                "ScriptWarp environment pointer is invalid", "transition-constructor-mismatch")
        self.events = []
        self.total = 0
        self.dropped = 0
        self.environment_free_seen = False
        self.failure = None
        self.closed = False
        self._heap_layout = None

    def _fail(self, message, attempt, error=None):
        if self.failure is None:
            details = {"heapFreeObservation": self.result(), "attempt": deepcopy(attempt)}
            if error is not None:
                details["readError"] = f"{type(error).__name__}: {error}"
            self.failure = DevtoolsFailure(
                "script-warp-heap-free-invalid", message, fatal=True, details=details)
        raise self.failure

    def _read_exact(self, address, size):
        require(_inside_main_ram(address, size),
                "Heap_Free telemetry read is outside main RAM", "script-warp-heap-free-invalid")
        data = self.session.read(address, size)
        require(isinstance(data, (bytes, bytearray)) and len(data) == size,
                "Heap_Free telemetry read is incomplete", "script-warp-heap-free-invalid")
        return bytes(data)

    def _layout(self):
        if self._heap_layout is not None:
            return self._heap_layout
        data = self._read_exact(HEAP_INFO, 28)
        (heap_handles, _parents, _raw, _counts, heap_indexes,
         total_heaps, templates, max_heaps, unallocated) = struct.unpack("<5I4H", data)
        require(0 < total_heaps <= 0x100 and 0 < max_heaps < 0x100
                and templates <= max_heaps and unallocated == max_heaps,
                "stock heap table limits are invalid", "script-warp-heap-free-invalid")
        require(heap_handles % 4 == 0 and _inside_main_ram(heap_handles, (max_heaps + 1) * 4),
                "stock heap handle table is invalid", "script-warp-heap-free-invalid")
        require(_inside_main_ram(heap_indexes, total_heaps),
                "stock heap index table is invalid", "script-warp-heap-free-invalid")
        self._heap_layout = {
            "heapHandles": heap_handles, "heapIndexes": heap_indexes,
            "totalHeaps": total_heaps, "maxHeaps": max_heaps,
        }
        return self._heap_layout

    def _script_warp_state(self):
        task_data = self._read_exact(self.task_pointer, 32)
        previous, function, task_state, environment, _, _, field, _ = struct.unpack("<8I", task_data)
        require(function == self.callback and environment == self.environment,
                "owned ScriptWarp task identity changed", "script-warp-heap-free-invalid")
        transition_state, map_id, warp_id, x, z, facing = struct.unpack(
            "<6i", self._read_exact(self.environment, 24))
        require(0 <= transition_state <= 3,
                "owned ScriptWarp transition state is invalid", "script-warp-heap-free-invalid")
        return {
            "taskPointer": self.task_pointer, "previous": previous, "function": function,
            "taskState": task_state, "environment": environment, "fieldPointer": field,
            "transitionState": transition_state, "mapId": map_id, "warpId": warp_id,
            "x": x, "z": z, "facing": facing,
        }

    def observe(self, pointer, caller, sp):
        # The owned environment free is the last point at which its state can
        # be read. Ignore later TaskManager cleanup instead of reading freed
        # environment storage.
        if self.closed or self.environment_free_seen:
            return
        attempt = {
            "pointer": pointer & 0xFFFFFFFF, "callerReturn": caller & 0xFFFFFFFF,
            "sp": sp & 0xFFFFFFFF, "frame": self.session.completed_frames,
            "nativeCycle": self.session.rt.EXECUTED_FRAME_COUNT,
        }
        try:
            pointer = attempt["pointer"]
            require(pointer % 4 == 0 and _inside_main_ram(pointer - 16, 16),
                    "Heap_Free pointer is invalid", "script-warp-heap-free-invalid")
            header_address = pointer - 16
            header_heap_id = self._read_exact(header_address, 16)[12]
            layout = self._layout()
            require(header_heap_id < layout["totalHeaps"],
                    "Heap_Free header heap ID is invalid", "script-warp-heap-free-invalid")
            heap_index = self._read_exact(layout["heapIndexes"] + header_heap_id, 1)[0]
            require(heap_index < layout["maxHeaps"],
                    "Heap_Free resolved an unallocated heap index", "script-warp-heap-free-invalid")
            resolved_handle = struct.unpack("<I", self._read_exact(
                layout["heapHandles"] + heap_index * 4, 4))[0]
            require(resolved_handle % 4 == 0 and _inside_main_ram(resolved_handle, 4),
                    "Heap_Free resolved a null or invalid heap handle", "script-warp-heap-free-invalid")
            event = {**attempt, "headerAddress": header_address,
                     "headerHeapId": header_heap_id, "heapIndex": heap_index,
                     "resolvedHandle": resolved_handle,
                     "scriptWarp": self._script_warp_state(),
                     "ownedEnvironmentFree": pointer == self.environment}
        except Exception as error:
            self._fail("prepared ScriptWarp Heap_Free telemetry rejected invalid state", attempt, error)
        self.total += 1
        self.environment_free_seen |= event["ownedEnvironmentFree"]
        self.events.append(event)
        if len(self.events) > MAX_EVENTS:
            self.events.pop(0)
            self.dropped += 1

    def check(self):
        if self.failure is not None:
            raise self.failure

    def finish(self):
        self.check()
        require(self.environment_free_seen,
                "completed ScriptWarp did not free its owned environment",
                "script-warp-heap-free-missing")
        self.closed = True
        return self.result()

    def result(self):
        return {
            "schemaVersion": 1,
            "scope": "read-only Heap_Free entries during one prepared ScriptWarp",
            "taskPointer": self.task_pointer,
            "environment": self.environment,
            "eventCount": self.total,
            "retainedEventCount": len(self.events),
            "droppedEventCount": self.dropped,
            "maximumRetainedEvents": MAX_EVENTS,
            "ownedEnvironmentFreeSeen": self.environment_free_seen,
            "closed": self.closed,
            "events": deepcopy(self.events),
        }


class QueryAllocationLifecycleObserver:
    """Boot-time receipts for the exact Query package and sole workspace.

    Use the existing entry/return hooks and heap walker. All reads happen at
    named native call boundaries. This class does not allocate in the guest,
    call guest code, write keys, or add frames. A missing owner is unknown.
    """

    PACKAGE_BYTES, RESERVE_BYTES = 70840, 32768
    CORE_BYTES, AUXILIARY_BYTES = 16600, 11268
    WORKSPACE_BYTES = CORE_BYTES + AUXILIARY_BYTES
    PACKAGE_HEAP_ID, CORE_HEAP_ID, WORKSPACE_HEAP_ID = 11, 11, 4
    CORE_RESERVE_BYTES, AUXILIARY_RESERVE_BYTES, ALLOCATION_MARGIN = 20480, 16384, 64
    MAX_ALLOCATIONS = 8
    HEAP_ALLOC, HEAP_FREE = 0x0201AA8C, 0x0201AB0C

    def __init__(self, session):
        self.session = session
        self.tokens, self.allocations = [], []
        self.rejected_allocation_request = None
        self.loads, self.acquires, self.drains, self.unloads = [], [], [], []
        self.destroys, self.allocation_failures = [], []
        self.destroy_token = None
        self.pending = self.current = None
        self.failure = None
        self.closed = False
        self.installed = False
        self.dynamic_token = None
        self.bodies = {}

    def _clock(self):
        return {"frame": self.session.completed_frames,
                "nativeCycle": self.session.rt.EXECUTED_FRAME_COUNT}

    def _read(self, address, size):
        require(type(address) is int and address % 4 == 0 and 0 < size <= 84
                and (_inside_main_ram(address, size)
                     or 0x027E0000 <= address <= 0x027E3FC0 - size),
                "Query lifecycle read range differs", "query-allocation-observation")
        raw = self.session.read(address, size)
        require(isinstance(raw, bytes) and len(raw) == size,
                "Query lifecycle read is incomplete", "query-allocation-observation")
        return raw

    def _word(self, address):
        return struct.unpack("<I", self._read(address, 4))[0]

    def _owner(self):
        owner = self.session._query_owner_diagnostics()
        require(owner.get("known") is True, "Query lifecycle owner is unknown",
                "query-allocation-observation")
        return owner

    def _heap(self, boundary, heap_id):
        capture = self.session._heap_diagnostics()
        rows = [row for row in capture.get("heaps", []) if row.get("heapId") == heap_id]
        require(capture.get("known") is True and len(rows) == 1 and rows[0].get("known") is True
                and rows[0].get("allocated") is True,
                f"Query lifecycle heap{heap_id} is unknown", "query-allocation-observation")
        # The same bounded walker runs while the guest is stopped in a native
        # callback. Do not mislabel this as a completed queue or paused API read.
        return {**deepcopy(rows[0]), **self._clock(), "boundary": boundary,
                "bytesRead": capture.get("bytesRead"),
                "readBudgetBytes": capture.get("readBudgetBytes"),
                "codeIdentity": deepcopy(capture.get("codeIdentity"))}

    def _runtime(self, field):
        from tools.overworld.devtools_query_observer import RUNTIME_SIZE
        state = self.session.rt.WILD_STATE
        actual_field, runtime = struct.unpack("<2I", self._read(state + 0xE0, 8))
        require(actual_field == field and runtime % 4 == 0
                and _inside_main_ram(runtime, RUNTIME_SIZE),
                "Query lifecycle Wild runtime owner differs", "query-allocation-observation")
        return runtime

    def _live(self, binding):
        address, body, dynamic = binding
        # Check the actual current occupant first. packaged_code also reads
        # live bytes, but only after this skip may it authenticate the ROM span.
        if self.session.read(address, len(body)) != body:
            return False
        if dynamic:
            return True
        return self.session.packaged_code(address, len(body)) == body

    def _watch(self, binding, before, after, *, scope=lambda: True):
        def enter():
            if self.closed or self.failure is not None:
                return None
            try:
                if not scope():
                    return None
                # Static overlay addresses can be occupied by another overlay
                # before/after the current Field. They confer no read ownership.
                if not self._live(binding):
                    require(not binding[2], "Query lifecycle relocated owner differs",
                            "query-allocation-observation")
                    return None
                return before()
            except Exception as error:
                self.failure = f"{type(error).__name__}: {error}"[:300]
                return None

        def leave(context):
            if self.failure is not None or self.closed:
                return
            try:
                require(self._live(binding), "Query lifecycle native owner changed before return",
                        "query-allocation-observation")
                after(context)
            except Exception as error:
                self.failure = f"{type(error).__name__}: {error}"[:300]

        token = self.session.party_getter_hooks.observe_call(binding[0], enter, leave)
        self.tokens.append(token)
        return token

    def _linked_ops(self, linked):
        from tools.overworld.devtools_field_cleanup import symbol
        from tools.overworld.devtools_runtime import _elf_code

        # This DATA object is packaged in the Wild overlay's executable .text.
        # The typed symbol reader returns no body for DATA; read its exact
        # section bytes, then bind them to this ROM before using the callbacks.
        address, size, _ = symbol(linked.read_bytes(), "sOverworldWildQueryCodeOps", 1,
                                  ".text", expected_size=24)
        body = _elf_code(linked, address, size)
        require(len(body) == size and any(
            base <= address <= base + len(data) - size
            and data[address - base:address - base + size] == body
            for base, data in self.session.code_regions),
            "Query lifecycle packaged native Ops differ", "query-allocation-observation")
        return address, body

    def install(self):
        import ndspy.narc
        import ndspy.rom
        from tools.overworld.devtools_field_cleanup import symbol
        from tools.overworld.devtools_query_observer import (
            sealed_package, QUERY_SIZE, QUERY_AUX_SIZE, READ_BUDGET, CARGO_CODE_END, BASE)
        from tools.overworld.devtools_runtime import _elf_code

        require(not self.installed, "Query lifecycle is already installed")
        build = self.session.rt.REPO / "build"
        self.elf = (build / "overworld_query_code_addon/image.elf").read_bytes()
        self.staged = (build / "overworld_query_code_addon/query.bin").read_bytes()
        self.member = ndspy.narc.NARC(ndspy.rom.NintendoDSRom.fromFile(str(self.session.rom))
                                     .getFileByName("a/0/2/8")).files[21]
        self.blob, self.image, self.receipt = sealed_package(self.elf, self.staged, self.member)
        require(len(self.blob) == self.PACKAGE_BYTES and QUERY_SIZE == self.CORE_BYTES and QUERY_AUX_SIZE == self.AUXILIARY_BYTES
                and READ_BUDGET == 0x9000 and CARGO_CODE_END <= 34944,
                "Query lifecycle final package/layout differs", "query-allocation-observation")
        address, size, body = symbol(self.elf, "AcquireQuery", 2)
        require(BASE + 196 <= address <= BASE + len(self.image) - size
                and body == self.image[address - BASE:address - BASE + size],
                "Query lifecycle workspace function owner differs", "query-allocation-observation")
        self.acquire_owner = (address, size, hashlib.sha256(body).hexdigest())
        address, size, body = symbol(self.elf, "DestroyQuery", 2)
        require(BASE + 196 <= address <= BASE + len(self.image) - size
                and body == self.image[address-BASE:address-BASE+size],
                "Query lifecycle destructor owner differs", "query-allocation-observation")
        self.destroy_owner = (address,size,hashlib.sha256(body).hexdigest())
        wild = build / "overworld_wild_spawns_overlay_linked.o"
        self.ops = self._linked_ops(wild)
        for key, file, name in (
            ("load", "overworld_wild_spawns_overlay_linked.o", "OverworldWildSpawns_LoadCodeAddonBlob"),
            ("discover", "overworld_wild_spawns_overlay_linked.o", "OverworldWildSpawns_QueryAddon"),
            ("drain", "overworld_wild_spawns_overlay_linked.o", "OverworldWildSpawns_DrainQuery"),
            ("unload", "overworld_follower_selector_overlay_linked.o", "OverworldQueryCodeAddon_Unload"),
        ):
            linked = build / file
            address, size, body = symbol(linked.read_bytes(), name, 2)
            require(body == _elf_code(linked, address, size)
                    and any(base <= address <= base + len(data) - size
                            and data[address - base:address - base + size] == body
                            for base, data in self.session.code_regions),
                    "Query lifecycle packaged native owner differs", "query-allocation-observation")
            self.bodies[key] = (address, body, False)
        require(struct.unpack("<6I", self.ops[1]) == (
            self.bodies["load"][0] | 1, self.HEAP_FREE | 1,
            0x020D2894, 0x020D28B8, 0x020D28D0, self.bodies["drain"][0] | 1),
            "Query lifecycle borrowed native Ops differ", "query-allocation-observation")
        # Full stock functions are already the current ROM's named stock owners.
        stock = (self.session.rt.REPO / "base/arm9.bin").read_bytes()
        for key, address, size in (("allocate", self.HEAP_ALLOC, 0x40),
                                   ("free", self.HEAP_FREE, 0x74)):
            body = stock[address - MAIN_RAM_START:address - MAIN_RAM_START + size]
            require(len(body) == size and self.session.packaged_code(address, size) == body,
                    "Query lifecycle stock allocator owner differs", "query-allocation-observation")
            self.bodies[key] = (address, body, False)
        self._watch(self.bodies["load"], self._load_before, self._load_after,
                    scope=lambda: self.session.emu.memory.register_arm9.r0 == 21)
        # Arm the return while still outside Load. The first QueryAddon entry
        # necessarily precedes the first cold package load.
        self._watch(self.bodies["discover"], lambda: {}, self._discover_after,
                    scope=lambda: self.current is None)
        self._watch(self.bodies["allocate"], self._allocate_before, self._allocate_after,
                    scope=lambda: bool(self.loads or self.acquires))
        self._watch(self.bodies["drain"], self._drain_before, self._drain_after,
                    scope=lambda: self.current is not None)
        self._watch(self.bodies["unload"], self._unload_before, self._unload_after,
                    scope=lambda: self.current is not None)
        self._watch(self.bodies["free"], self._free_before, self._free_after,
                    scope=lambda: bool(self.drains or self.unloads or self.acquires or self.destroys))
        self.installed = True

    def _load_before(self):
        regs = self.session.emu.memory.register_arm9
        owner = self._owner()
        require(regs.r1 == self.PACKAGE_BYTES and owner["rawHex"] == bytes(28).hex()
                and self.pending is None and self.current is None,
                "Query lifecycle load is not cold", "query-allocation-observation")
        value = {"field": self.session.field_pointer(), "ownerBefore": owner,
                 "heapBeforeLoad": self._heap("native-LoadCodeAddonBlob-entry", self.PACKAGE_HEAP_ID),
                 "blobOut": regs.r2, "sizeOut": regs.r3, "allocation": None, **self._clock()}
        self.loads.append(value)
        self.pending = value
        return value

    def _load_after(self, value):
        require(self.loads and self.loads.pop() is value and self.pending is value,
                "Query lifecycle load interval differs", "query-allocation-observation")
        require(self.session.emu.memory.register_arm9.r0 == 1 and value["allocation"] is not None
                and self._word(value["blobOut"]) == value["allocation"]["pointer"]
                and self._word(value["sizeOut"]) == self.PACKAGE_BYTES,
                "Query lifecycle package load did not return its allocation", "query-allocation-observation")
        value.update(loaded=True, heapAfterLoad=self._heap(
            "native-LoadCodeAddonBlob-return", self.PACKAGE_HEAP_ID))
        value["allocation"].update(heapBeforeLoad=value["heapBeforeLoad"],
                                   heapAfterLoad=value["heapAfterLoad"], ownerBeforeLoad=value["ownerBefore"])

    def _discover_after(self, _entry):
        from tools.overworld.devtools_query_observer import (
            authenticate_loaded_query_functions, relocated_image, BASE)
        value = self.pending
        if value is None:
            return
        require(value.get("loaded") is True, "Query lifecycle cold load did not complete",
                "query-allocation-observation")
        owner = authenticate_loaded_query_functions(self.session, self.elf, self.staged,
            self.member, {"AcquireQuery": self.acquire_owner, "DestroyQuery": self.destroy_owner})
        require(value is self.pending and self.session.emu.memory.register_arm9.r0 == owner["entry"],
                "Query lifecycle published return differs", "query-allocation-observation")
        full = self._owner()
        require(full["blob"] == value["allocation"]["pointer"] and full["fieldIdentity"] == value["field"],
                "Query lifecycle publication lost its allocation/Field", "query-allocation-observation")
        value["allocation"].update(ownerPublished=full)
        # The image can load before the Wild runtime is created. Its later
        # actual Acquire call supplies that separate current owner.
        value.update(owner=full, runtime=None)
        self.current, self.pending = value, None
        address, size, _sha = self.acquire_owner
        offset = address - BASE
        image = relocated_image(self.image, self.receipt, owner["entry"])
        self.bodies["acquire"] = (owner["entry"] + offset, image[offset:offset + size], True)
        self.dynamic_token = self._watch(self.bodies["acquire"], self._acquire_before,
            self._acquire_after, scope=self._needs_workspace)
        address,size,_sha=self.destroy_owner
        offset=address-BASE
        self.bodies["destroy"]=(owner["entry"]+offset,image[offset:offset+size],True)
        self.destroy_token=self._watch(self.bodies["destroy"],self._destroy_before,self._destroy_after,
            scope=lambda: self.current is not None)

    def _needs_workspace(self):
        from tools.overworld.devtools_query_observer import RUNTIME_QUERY
        return self.current is not None and (self.current["runtime"] is None
            or self._word(self.current["runtime"] + RUNTIME_QUERY) == 0)

    def _acquire_before(self):
        from tools.overworld.devtools_query_observer import RUNTIME_QUERY
        regs=self.session.emu.memory.register_arm9
        call=self._read(regs.r0,32)
        world,_profile,_options,allocate,free_size,heap=struct.unpack_from("<6I",call)
        version,size,field,state=struct.unpack_from("<HH2I",self._read(world,84))
        require((version,size,state,field,heap,allocate,free_size)==(3,84,self.session.rt.WILD_STATE,
            self.current["field"],self.WORKSPACE_HEAP_ID,self.HEAP_ALLOC|1,0x0201ABED),
            "Query lifecycle borrowed allocation call differs","query-allocation-observation")
        owner=self._owner();runtime=self._runtime(owner["fieldIdentity"])
        require(owner["phase"]==1 and owner["blob"]==self.current["allocation"]["pointer"]
            and owner["fieldIdentity"]==self.current["field"]
            and (self.current["runtime"] is None or runtime==self.current["runtime"]),
            "Query lifecycle workspace owner differs","query-allocation-observation")
        self.current["runtime"]=runtime
        if self._word(runtime+RUNTIME_QUERY):return None
        value=dict(runtime=runtime,ownerBefore=owner,allocation=None,auxiliary=None,
            failedCore=False,failedAuxiliary=False)
        self.acquires.append(value)
        return value

    def _acquire_after(self,value):
        from tools.overworld.devtools_query_observer import RUNTIME_QUERY,workspace_allocation
        require(self.acquires and self.acquires.pop() is value,
            "Query lifecycle Acquire interval differs","query-allocation-observation")
        returned=self.session.emu.memory.register_arm9.r0
        published=self._word(value["runtime"]+RUNTIME_QUERY)
        core,aux=value["allocation"],value["auxiliary"]
        if returned==0:
            require(published==0 and aux is None and (core is None or
                value["failedAuxiliary"] and core["freeCount"]==1),
                "Query lifecycle failed second allocation was published or not rolled back",
                "query-allocation-observation")
            if core is not None:core.update(rolledBack=True,published=False)
            return
        require(core is not None and aux is not None and not value["failedCore"] and not value["failedAuxiliary"]
            and returned==published==core["pointer"] and core["freeCount"]==aux["freeCount"]==0,
            "Query lifecycle both chunks were not owned before publication","query-allocation-observation")
        prefix=workspace_allocation(self._read,returned,self.bodies["destroy"][0]|1)
        require(prefix["auxiliary"]==aux["pointer"],
            "Query lifecycle published a foreign auxiliary","query-allocation-observation")
        owner=self._owner()
        require(owner==value["ownerBefore"],"Query lifecycle publication changed its full owner","query-allocation-observation")
        core.update(runtime=value["runtime"],published=True,ownerPublished=owner,
                    auxiliary=aux["pointer"],prefix=prefix)
        aux.update(runtime=value["runtime"],published=True,ownerPublished=owner,core=core["pointer"])

    def _allocate_before(self):
        regs=self.session.emu.memory.register_arm9
        if self.acquires:
            context=self.acquires[-1]
            kind,expected,heap_id,reserve=("workspace-core",self.CORE_BYTES,self.CORE_HEAP_ID,self.CORE_RESERVE_BYTES) if context["allocation"] is None else (
                "workspace-auxiliary",self.AUXILIARY_BYTES,self.WORKSPACE_HEAP_ID,self.AUXILIARY_RESERVE_BYTES)
            field="allocation" if kind=="workspace-core" else "auxiliary"
            binding=self.bodies["acquire"];margin=self.ALLOCATION_MARGIN
        else:
            context=self.loads[-1];kind,expected,heap_id,reserve="package",self.PACKAGE_BYTES,self.PACKAGE_HEAP_ID,self.RESERVE_BYTES
            field="allocation";binding=self.bodies["load"];margin=0
        if regs.r1!=expected:return None
        require(regs.r0==heap_id and regs.lr&1 and binding[0]<=(regs.lr&~1)<binding[0]+len(binding[1])
            and context[field] is None and len(self.allocations)+len(self.allocation_failures)<self.MAX_ALLOCATIONS,
            "Query lifecycle allocator call/limit differs","query-allocation-observation")
        heap=self._heap("native-Heap_Alloc-entry",heap_id)
        insufficient=heap["totalFreeBytes"]<expected+reserve+margin
        fragmented=heap["largestUserAllocationBytes"]<expected
        if (insufficient or fragmented) and self.rejected_allocation_request is None:
            self.rejected_allocation_request=dict(kind=kind,bytes=expected,heapId=regs.r0,callerReturn=regs.lr,
                heapBeforeAllocation=deepcopy(heap),ownerBefore=deepcopy(context["ownerBefore"]),
                insufficientReserve=insufficient,insufficientContiguousSpace=fragmented,nativeReturnObserved=False,**self._clock())
        require(not insufficient and (kind!="package" or not fragmented),"Query lifecycle allocation has insufficient reserve/contiguous space","query-allocation-observation")
        return dict(kind=kind,bytes=expected,heapId=heap_id,reserveBytes=reserve,allocationMargin=margin,
            context=context,contextField=field,heapBeforeAllocation=heap,callerReturn=regs.lr,**self._clock())

    def _allocate_after(self,value):
        pointer=self.session.emu.memory.register_arm9.r0
        heap=self._heap("native-Heap_Alloc-return",value["heapId"])
        context=value.pop("context");field=value.pop("contextField")
        value.update(ownerBefore=deepcopy(context["ownerBefore"]),runtime=context.get("runtime"))
        if pointer==0:
            before=value["heapBeforeAllocation"]
            require(value["kind"]!="package" and heap["handle"]==before["handle"]
                and heap["allocationCount"]==before["allocationCount"] and heap["totalFreeBytes"]==before["totalFreeBytes"],
                "Query lifecycle failed allocation changed heap ownership","query-allocation-observation")
            context["failedCore" if field=="allocation" else "failedAuxiliary"]=True
            value.update(pointer=0,nativeReturnObserved=True,heapAfterAllocation=heap,allocationReturned=self._clock())
            self.allocation_failures.append(value)
            if self.rejected_allocation_request is not None:self.rejected_allocation_request["nativeReturnObserved"]=True
            return
        require(pointer%4==0 and heap["heapStart"]<=pointer-16 and pointer+value["bytes"]<=heap["heapEnd"]
            and self._read(pointer-16,16)[12]==value["heapId"]
            and heap["handle"]==value["heapBeforeAllocation"]["handle"]
            and heap["allocationCount"]==value["heapBeforeAllocation"]["allocationCount"]+1
            and heap["totalFreeBytes"]>=value["reserveBytes"]
            and (not value["allocationMargin"] or value["heapBeforeAllocation"]["totalFreeBytes"]-heap["totalFreeBytes"]<=value["bytes"]+value["allocationMargin"])
            and value["heapBeforeAllocation"]["largestUserAllocationBytes"]>=value["bytes"],
            "Query lifecycle allocation/header/reserve differs","query-allocation-observation")
        value.update(pointer=pointer,heapAfterAllocation=heap,freeCount=0,allocationReturned=self._clock())
        context[field]=value;self.allocations.append(value)

    def _drain_before(self):
        from tools.overworld.devtools_query_observer import RUNTIME_QUERY,workspace_allocation
        runtime=self.session.emu.memory.register_arm9.r0
        require(runtime==(self.current["runtime"] or 0),"Query lifecycle drain runtime differs","query-allocation-observation")
        pointer=self._word(runtime+RUNTIME_QUERY) if runtime else 0
        owned=[r for r in self.allocations if r["kind"]=="workspace-core" and r["pointer"]==pointer and r["freeCount"]==0 and r.get("published")]
        require(not pointer or len(owned)==1,"Query lifecycle drain has an unobserved workspace","query-allocation-observation")
        core=owned[0] if owned else None;aux=None;prefix=None
        if core is not None:
            prefix=workspace_allocation(self._read,pointer,self.bodies["destroy"][0]|1)
            rows=[r for r in self.allocations if r["kind"]=="workspace-auxiliary" and r["pointer"]==prefix["auxiliary"] and r["freeCount"]==0 and r.get("core")==pointer]
            require(len(rows)==1,"Query lifecycle drain lost its auxiliary owner","query-allocation-observation")
            aux=rows[0]
        value=dict(runtime=runtime,allocation=core,auxiliary=aux,prefix=prefix,ownerBefore=self._owner(),destructorSeen=False,destructorReturned=False)
        self.drains.append(value);return value

    def _drain_after(self,value):
        from tools.overworld.devtools_query_observer import RUNTIME_QUERY
        require(self.drains and self.drains.pop() is value and self.session.emu.memory.register_arm9.r0==1
            and (not value["runtime"] or self._word(value["runtime"]+RUNTIME_QUERY)==0)
            and (value["allocation"] is None or value["destructorSeen"] and value["destructorReturned"]
                and value["allocation"]["freeCount"]==value["auxiliary"]["freeCount"]==1),
            "Query lifecycle drain did not destroy both chunks/clear once","query-allocation-observation")
        for key in ("allocation","auxiliary"):
            if value[key] is not None:value[key].update(drained=True,drainReturned=self._clock())

    def _destroy_before(self):
        from tools.overworld.devtools_query_observer import RUNTIME_QUERY,workspace_allocation
        require(self.drains,"Query lifecycle destructor has no native drain","query-allocation-observation")
        value=self.drains[-1];core=value["allocation"]
        require(core is not None and not value["destructorSeen"] and self.session.emu.memory.register_arm9.r0==core["pointer"]
            and self._word(value["runtime"]+RUNTIME_QUERY)==0 and self._owner()==value["ownerBefore"],
            "Query lifecycle destructor lost its cleared current full owner","query-allocation-observation")
        require(workspace_allocation(self._read,core["pointer"],self.bodies["destroy"][0]|1)==value["prefix"],
            "Query lifecycle destructor prefix changed","query-allocation-observation")
        value["destructorSeen"]=True;self.destroys.append(value);return value

    def _destroy_after(self,value):
        require(self.destroys and self.destroys.pop() is value
            and value["allocation"]["freeCount"]==value["auxiliary"]["freeCount"]==1,
            "Query lifecycle destructor did not free auxiliary then core","query-allocation-observation")
        value["destructorReturned"]=True

    def _unload_before(self):
        from tools.overworld.devtools_query_observer import RUNTIME_QUERY
        regs = self.session.emu.memory.register_arm9
        owner = self._owner()
        runtime = self.current["runtime"]
        if runtime is None and regs.r2:
            # A cold image may be unloaded after runtime creation but before
            # AcquireQuery. Bind only the current Field's empty workspace.
            require(owner["fieldIdentity"] == self.current["field"],
                    "Query lifecycle Unload owner differs", "query-allocation-observation")
            runtime = self._runtime(owner["fieldIdentity"])
            require(regs.r2 == runtime and self._word(runtime + RUNTIME_QUERY) == 0,
                    "Query lifecycle Unload owner differs", "query-allocation-observation")
        require(regs.r0 == 0x023C2308 and regs.r1 == self.ops[0]
                and regs.r2 == (runtime or 0)
                and self.session.packaged_code(self.ops[0], 24) == self.ops[1]
                and owner["blob"] == self.current["allocation"]["pointer"]
                and owner["phase"] in (1, 2), "Query lifecycle Unload owner differs",
                "query-allocation-observation")
        self.current["runtime"] = runtime
        value = {"allocation": self.current["allocation"], "ownerBefore": owner}
        self.unloads.append(value)
        return value

    def _unload_after(self, value):
        require(self.unloads and self.unloads.pop() is value
                and self.session.emu.memory.register_arm9.r0 == 0
                and self._owner()["rawHex"] == bytes(28).hex()
                and value["allocation"]["freeCount"] == 1,
                "Query lifecycle Unload did not free/clear once", "query-allocation-observation")
        value["allocation"].update(unloaded=True, unloadReturned=self._clock())
        self.current = None
        for name in ("dynamic_token","destroy_token"):
            token=getattr(self,name)
            if token is not None:
                self.session.party_getter_hooks.remove(token)
                if token in self.tokens:self.tokens.remove(token)
                setattr(self,name,None)

    def _free_before(self):
        from tools.overworld.devtools_query_observer import RUNTIME_QUERY
        regs=self.session.emu.memory.register_arm9
        candidates=[r for r in self.allocations if r["pointer"]==regs.r0 and r["freeCount"]==0]
        if not candidates:
            require(not any(r["pointer"]==regs.r0 for r in self.allocations),
                "Query lifecycle owned allocation was freed twice","query-allocation-observation")
            return None
        require(len(candidates)==1 and candidates[0]["freeCount"]==0,
            "Query lifecycle owned allocation was freed twice","query-allocation-observation")
        allocation=candidates[0];owner=self._owner()
        if allocation["kind"]=="package":
            require(self.unloads and owner["rawHex"]==bytes(28).hex()
                and all(r["freeCount"]==1 for r in self.allocations if r["kind"]!="package"),
                "Query lifecycle free/owner-clear order differs","query-allocation-observation")
            binding=self.bodies["unload"]
        elif self.destroys:
            value=self.destroys[-1];core,aux=value["allocation"],value["auxiliary"]
            require(allocation in (core,aux) and owner==value["ownerBefore"] and owner["phase"] in (2,3)
                and owner["blob"]==self.current["allocation"]["pointer"]
                and self._word(value["runtime"]+RUNTIME_QUERY)==0 and self._read(core["pointer"],12)==bytes(12)
                and (core["freeCount"]==0 if allocation is aux else aux["freeCount"]==1),
                "Query lifecycle nested free/prefix/auxiliary-first order differs","query-allocation-observation")
            binding=self.bodies["destroy"]
        else:
            value=self.acquires[-1] if self.acquires else None
            require(value is not None and allocation is value["allocation"] and value["failedAuxiliary"]
                and value["auxiliary"] is None and owner==value["ownerBefore"] and owner["phase"]==1
                and self._word(value["runtime"]+RUNTIME_QUERY)==0,
                "Query lifecycle free is outside owned destructor/rollback","query-allocation-observation")
            binding=self.bodies["acquire"]
        require(regs.lr&1 and binding[0]<=(regs.lr&~1)<binding[0]+len(binding[1])
            and self._read(regs.r0-16,16)[12]==allocation["heapId"],
            "Query lifecycle free caller/header differs","query-allocation-observation")
        heap=self._heap("native-Heap_Free-entry",allocation["heapId"])
        require(heap["handle"]==allocation["heapAfterAllocation"]["handle"],
            "Query lifecycle free heap owner changed","query-allocation-observation")
        return dict(allocation=allocation,callerReturn=regs.lr,heapBeforeFree=heap,**self._clock())

    def _free_after(self, value):
        allocation = value["allocation"]
        heap = self._heap("native-Heap_Free-return", allocation["heapId"])
        before = value["heapBeforeFree"]
        require(allocation["freeCount"] == 0 and heap["handle"] == before["handle"]
                and heap["allocationCount"] == before["allocationCount"] - 1
                and heap["totalFreeBytes"] >= before["totalFreeBytes"] + allocation["bytes"],
                f"Query lifecycle exact free was not returned to heap{allocation['heapId']}",
                "query-allocation-observation")
        allocation.update(freeCount=1, freeEntry={key: item for key, item in value.items() if key != "allocation"},
                          heapAfterFree=heap, freeReturned=self._clock())

    def result(self):
        complete=any(r["kind"]=="workspace-core" and r.get("published") for r in self.allocations)
        complete=complete and all(r["freeCount"]==1 and (r.get("unloaded") if r["kind"]=="package" else
            r.get("drained") or r.get("rolledBack")) for r in self.allocations)
        complete=complete and self.pending is None and self.current is None and not self.destroys and not self.acquires
        return dict(schemaVersion=2,diagnosticOnly=True,acceptedProof=False,
            known=self.installed and self.failure is None,complete=bool(complete and self.failure is None),
            reason=self.failure,attachedBeforeBoot=self.installed,packageBytes=self.PACKAGE_BYTES,
            workspaceBytes=self.WORKSPACE_BYTES,workspaceCoreBytes=self.CORE_BYTES,workspaceAuxiliaryBytes=self.AUXILIARY_BYTES,
            packageHeapId=self.PACKAGE_HEAP_ID,workspaceCoreHeapId=self.CORE_HEAP_ID,workspaceHeapId=self.WORKSPACE_HEAP_ID,
            reserveBytes=self.RESERVE_BYTES,workspaceCoreReserveBytes=self.CORE_RESERVE_BYTES,
            workspaceAuxiliaryReserveBytes=self.AUXILIARY_RESERVE_BYTES,allocationMargin=self.ALLOCATION_MARGIN,
            maximumAllocations=self.MAX_ALLOCATIONS,allocations=deepcopy(self.allocations),
            failedAllocations=deepcopy(self.allocation_failures),rejectedAllocationRequest=deepcopy(self.rejected_allocation_request),closed=self.closed,
            scope="exact cold Query package on heap11; versioned core on heap11 plus auxiliary on heap4; rollback and nested destructor before code unload")

    def close(self):
        self.closed = True
        for token in self.tokens:
            self.session.party_getter_hooks.remove(token)
        self.tokens.clear()
