"""Two bounded native route faults; no setup, input loop or proof decision."""
from copy import deepcopy
import struct
import time

from tools.overworld.devtools_records import GENERATION_FIELDS, _subject


class RouteControlFailure(RuntimeError):
    code = "route-control-failed"

    def __init__(self, message, details, fatal=False):
        super().__init__(message)
        self.details, self.fatal = details, fatal


class NativeRouteControl:
    CPU_WORK_NS = 100_000_000

    def __init__(self, session, subject):
        self.session, self.subject = session, _subject(subject)
        if self.subject["species"] != 155 or self.subject["role"] != "FOLLOWER" or self.subject["handle"]["slot"] != 7:
            raise ValueError("route control requires the exact FOLLOWER Cyndaquil")
        self.state, self.kind = "new", None
        self.receipts, self.failure = [], None
        self.binding = self.pinned = None
        self.closed = self.requires_core_close = False
        self.armed_frame = self.last_frame = self.max_frames = self.cpu_cycle = None
        self.writes = 0

    def _fail(self, message):
        self.failure = self.failure or {"message": message, "frame": self.session.completed_frames}
        self.state = "failed"
        raise RouteControlFailure(message, self.result(), self.requires_core_close)

    def _current(self):
        from tools.overworld.devtools_runtime import actor_identity_checks
        s, rt = self.session, self.session.rt
        if self.closed or self.failure or s.emu is None or s.closed or s.native_bridge_active:
            self._fail("route control has no available native field boundary")
        try:
            descriptor = rt.ACTOR_DESCRIPTOR["state"]
            if descriptor["offsets"].get("fieldEpoch") != 12 or descriptor["offsets"].get("mapGeneration") != 46 \
                    or rt.unsigned(s.emu, descriptor["address"]) != 0x5353574F:
                self._fail("route control context ABI differs")
            context = {"fieldEpoch": rt.unsigned(s.emu, descriptor["address"]+12,2),
                       "mapGeneration": rt.unsigned(s.emu, descriptor["address"]+46,2),
                       "mapId": rt.field_map_id(s.emu)}
            actor, source, engine = rt.actor_state(s.emu,7), rt.wild_spawn(s.emu,7), rt.live_wild_object_identity(s.emu,7)
            if actor.get("active") is not True or _subject(actor) != self.subject \
                    or not all(actor_identity_checks(actor,source,engine,context,7).values()) \
                    or source["object"] != engine["pointer"] or actor.get("form") != source.get("form") \
                    or actor.get("level") != source.get("level"):
                self._fail("route control follower identity changed")
            pointer, manager = rt.player_ptr(s.emu), engine["current_manager"]
            if type(pointer) is not int or pointer & 3 or not 0x02000000 <= pointer <= 0x02400000-0x12C \
                    or type(manager) is not int or manager & 3 or not 0x02000000 <= manager <= 0x02400000-0x128:
                self._fail("route control player or manager span differs")
            objects, count = rt.unsigned(s.emu,manager+0x124),rt.unsigned(s.emu,manager+4)
            delta = pointer-objects
            pose = rt.object_state(s.emu,pointer)
            if not 1 <= count <= 1024 or objects & 3 or not 0x02000000 <= objects <= 0x02400000-count*0x12C \
                    or delta < 0 or delta % 0x12C or delta//0x12C >= count \
                    or rt.unsigned(s.emu,pointer+0xB4) != manager or not pose["flags"] & 1 \
                    or pointer == source["object"]:
                self._fail("route control player is not the active unmounted manager object")
            binding = {"context":context,"playerPointer":pointer,"playerManager":manager,
                       "followerPointer":source["object"],"sourceIdentity":{key:source[key] for key in
                           ("object","personality","map_id","species","form","level","active","object_id","encounter_generation")},
                       "generations":{key:actor[key] for key in GENERATION_FIELDS}}
            if self.binding is not None and binding != self.binding:
                self._fail("route control native ownership changed")
            return binding, pose
        except RouteControlFailure:
            raise
        except Exception as error:
            self._fail("route control native read failed: " + str(error)[:160])

    def _receipt(self, action, **fields):
        if len(self.receipts) >= 128:
            self._fail("route control receipt bound exceeded")
        row = {"action":action,"kind":self.kind,"frame":self.session.completed_frames,
               "nativeCycle":self.session.rt.EXECUTED_FRAME_COUNT,"subject":deepcopy(self.subject),
               **deepcopy(self.binding or {}), **deepcopy(fields)}
        self.receipts.append(row)
        return deepcopy(row)

    def arm(self, kind, max_frames=32):
        if type(max_frames) is not int or not 1 <= max_frames <= 120:
            raise ValueError("route control frame bound must be 1..120")
        if kind not in ("cpu-hitch","player-start-stall"):
            raise ValueError("unknown route control")
        expected = "new" if kind == "cpu-hitch" else "cpu-injected"
        if self.state != expected or kind == "player-start-stall" and self.session.rt.EXECUTED_FRAME_COUNT < self.cpu_cycle:
            self._fail("route control faults are out of order")
        binding,_ = self._current()
        self.binding = binding
        self.kind, self.max_frames = kind,max_frames
        self.armed_frame = self.last_frame = self.session.completed_frames
        self.state = "cpu-armed" if kind == "cpu-hitch" else "player-armed"
        self._receipt("armed",maxFrames=max_frames)
        return self.result()

    def before_cycle(self):
        """Parent must call inside the real cycle's process-time interval."""
        if self.state != "cpu-armed": return
        self._current()
        if self.session.completed_frames-self.armed_frame > self.max_frames:
            self._fail("route CPU control deadline expired")
        before = self.session.rt.EXECUTED_FRAME_COUNT
        start = time.process_time_ns()
        value = 1
        for _ in range(2_000_000):
            value = (value*1664525+1013904223) & 0xFFFFFFFF
            if time.process_time_ns()-start >= self.CPU_WORK_NS: break
        end = time.process_time_ns()
        if end-start < self.CPU_WORK_NS:
            self._fail("bounded CPU work did not reach its measured duration")
        self.cpu_cycle = before+1
        self.state = "cpu-injected"
        self._receipt("cpu-work",nativeCycleBefore=before,targetNativeCycle=self.cpu_cycle,
                      workStartCpuNs=start,workEndCpuNs=end,workCpuNs=end-start)

    def player_step_admitted(self, receipt):
        if self.state not in ("player-armed","player-pinning"): return
        binding,_ = self._current()
        if self.session.completed_frames-self.armed_frame > self.max_frames:
            self._fail("route player admission deadline expired")
        if self.pinned is not None:
            self._fail("route control received another player admission")
        before,after = receipt.get("objectBefore",{}),receipt.get("objectAfter",{})
        origin,target = receipt.get("origin"),receipt.get("target")
        if receipt.get("objectPointer") != binding["playerPointer"] or receipt.get("mapId") != binding["context"]["mapId"] \
                or origin != [before.get("x"),before.get("y")] or target != [after.get("x"),after.get("y")] \
                or not isinstance(origin,list) or not isinstance(target,list) or len(origin)!=2 or len(target)!=2 \
                or any(type(v) is not int for v in origin+target) or sum(abs(a-b) for a,b in zip(origin,target))!=1 \
                or [after.get("x_prev"),after.get("y_prev")] != origin \
                or [before.get("pos_x"),before.get("pos_z")] != [after.get("pos_x"),after.get("pos_z")] \
                or [before.get("pos_x"),before.get("pos_z")] != [v*65536+32768 for v in origin]:
            self._fail("route control admission does not own an exact origin and cardinal target")
        self.pinned = [before["pos_x"],before["pos_z"]]
        self.state = "player-pinning"
        self._receipt("player-admitted",admission=receipt,pinned=self.pinned)

    def completed_boundary(self):
        if self.state not in ("player-armed","player-pinning"): return
        binding,pose = self._current()
        frame = self.session.completed_frames
        if frame == self.last_frame:return
        if frame != self.last_frame+1 or frame-self.armed_frame > self.max_frames:
            self._fail("route player control missed a frame or exceeded its limit")
        self.last_frame = frame
        if self.pinned is None:return
        self.requires_core_close = True
        self.session.route_control_nonresumable = True
        pointer = binding["playerPointer"]
        try:
            for offset,value in zip((0x70,0x78),self.pinned):
                self.session.rt.actor_memory_write(self.session.emu,pointer+offset,struct.pack("<i",value))
            actual = self.session.rt.object_state(self.session.emu,pointer)
            if [actual["pos_x"],actual["pos_z"]] != self.pinned:
                self._fail("route control pin readback differs")
        except RouteControlFailure:raise
        except Exception as error:self._fail("route control pin write failed: "+str(error)[:160])
        self.writes += 1
        return self._receipt("player-pinned",before=[pose["pos_x"],pose["pos_z"]],after=self.pinned,writeIndex=self.writes)

    def close(self):
        if not self.closed:
            self._receipt("closed",requiresCoreClose=self.requires_core_close)
            self.closed=True
            self.state="closed" if self.failure is None else "failed"
        return self.result()

    def result(self):
        return {"type":"native-route-control-v1","state":self.state,"kind":self.kind,
                "subject":deepcopy(self.subject),"receipts":deepcopy(self.receipts),
                "failure":deepcopy(self.failure),"closed":self.closed,"requiresCoreClose":self.requires_core_close}
