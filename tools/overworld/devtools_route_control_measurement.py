"""Live calibration of the unchanged cadence checks, not a short S5 pass."""
from copy import deepcopy

from tools.overworld.devtools_cadence_measurement import UnmountedCadenceMeasurement
from tools.overworld.devtools_raw_chunk import validate_raw_chunk
from tools.overworld.devtools_records import select_current_actor
from tools.overworld.runtime_cadence import classify_frame_hitches, classify_player_motion


def same_subject(a, b):
    return isinstance(a, dict) and isinstance(b, dict) and all(
        a.get(k) == b.get(k) for k in ("handle", "species", "role", "subjectIdentity"))


def integer(value, low=0, high=0xFFFFFFFFFFFFFFFF):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("invalid route-control integer")
    return value


class _ControlCadence(UnmountedCadenceMeasurement):
    """Only receipted expected failures are classified separately."""
    def _events(self, events, frame, snapshot=None):
        self.control_frame = frame
        admissions = super()._events(events, frame, snapshot)
        owner = self.control_owner
        if owner.armed_kind=="player-start-stall":
            envelope={"observation","sequence","entryActorFrame","entryNativeCycle",
                      "returnActorFrame","returnNativeCycle","setupMode","returnValue"}
            for data in admissions:
                if owner.native_admission is not None:
                    raise ValueError("player control admitted more than one motion")
                owner.native_admission={k:deepcopy(v) for k,v in data.items() if k not in envelope}
                owner.native_admission_frame=frame
        if owner.armed_kind:
            owner._control(snapshot.get("routeControl"),snapshot)
            if frame-owner.arm_frame>120:
                raise ValueError("route control exceeded its arm budget")
        elif snapshot.get("routeControl") is not None:
            raise ValueError("native route control appeared before its sealed arm")
        return admissions

    def _cpu_check(self):
        self.hitches = classify_frame_hitches(self.route_cpu, 2000, 250000)
        self.last_cpu_check = len(self.route_cpu)
        unexpected = list(self.hitches["hitchFrames"])
        owner = self.control_owner
        if owner.cpu_work is not None:
            target = owner.cpu_work["targetNativeCycle"]
            indices = [i for i, cycle in enumerate(owner.route_cycles[:len(self.route_cpu)]) if cycle == target]
            if len(indices) == 1 and indices[0] in unexpected:
                index = indices[0]
                if self.route_cpu[index] < owner.cpu_work["workCpuNs"]:
                    super()._fail("route-control-cpu-receipt-exceeds-interval")
                    return
                unexpected.remove(index)
                owner.detections.setdefault("cpu-hitch", {"nativeCycle":target,"intervalIndex":index,
                    "cpuNs":self.route_cpu[index],"receipt":deepcopy(owner.cpu_work),
                    "cpuSamples":list(self.route_cpu),
                    "nativeCycles":list(owner.route_cycles[:len(self.route_cpu)]),
                    "classifier":deepcopy(self.hitches)})
        if unexpected:
            super()._fail("host-process-cpu-hitch", self.hitches)

    def _fail(self, code, detail=None, *, gap=False, frame=None):
        owner = self.control_owner
        if code == "player-render-start-stall" and owner.armed_kind == "player-start-stall":
            try:
                owner._player_detection(self)
                return
            except (ValueError, KeyError, TypeError) as error:
                detail = {"original":detail,"controlError":str(error)}
        super()._fail(code, detail, gap=gap, frame=frame if frame is not None else getattr(self,"control_frame",None))


class _EndPlayerFaultChunk(RuntimeError):
    """Leave the underlying sample loop before any later sample is consumed."""


class LiveRouteControlMeasurement:
    def __init__(self, test, *, max_frames, setup_transitions=()):
        if test.get("mode") != "observer-control":
            raise ValueError("live route calibration requires observer-control mode")
        self.actions = {(phase,a["id"]):deepcopy(a) for phase,name in
                        (("setup","setup"),("observe","actions")) for a in test.get(name,[])}
        local = deepcopy(test); local["mode"] = "prepared"
        for name in ("setup","actions"):
            local[name] = [a for a in local.get(name,[]) if a["op"] != "observer-control"]
        self.baseline = _ControlCadence(local,max_frames=max_frames,setup_transitions=setup_transitions)
        self.baseline.control_owner = self
        self.max_frames = max_frames
        self.baseline_result = None
        self.first_three_held = False
        self.route_cycles = []
        self.histories = []
        self.cpu_work = None
        self.admission = None
        self.native_admission = None
        self.native_admission_frame = None
        self.pins = []
        self.detections = {}
        self.armed_kind = None
        self.arm_frame = None
        self.arm_cycle = None
        self.owner_binding = None
        self.cleanup = None
        self.closed = False
        self.control_failures = []

    def __getattr__(self, name):
        if name == "baseline": raise AttributeError(name)
        return getattr(self.baseline, name)

    def _fail(self, error):
        if not self.control_failures:
            self.control_failures.append({"code":"live-route-control-invalid","detail":str(error),
                "frame":self.latest.get("frame") if self.latest else None})

    def stage(self, name):
        return not self.control_failures and not self.baseline.failures and {
            "baseline":self.baseline_result is not None,
            "cpu-detected":"cpu-hitch" in self.detections and self._settled(),
            "player-detected":"player-start-stall" in self.detections,
            "complete":len(self.detections)==2 and self.cleanup is not None}.get(name,False)

    def _settled(self):
        return self.step is None and self.recorder.current is None and self.crash_presentation.ready \
            and self.actor is not None and self.actor.get("motionPhase")=="IDLE" \
            and all("canceledMotion" not in h or "recoveryTerminal" in h for h in self.handoffs)

    def _seal_baseline(self):
        meter = self.baseline
        if meter.player_motions <= 3 and meter.held_tiles:
            self.first_three_held = True
        if self.baseline_result is not None or meter.failures:
            return
        cpu = classify_frame_hitches(meter.route_cpu,2000,250000)
        if meter.player_motions >= 4 and self.first_three_held and meter.follower_motions >= 1 \
                and meter.step is None and meter.recorder.current is None and meter.crash_presentation.ready \
                and len(meter.route_cpu)>=16 and cpu["hitchCount"] == 0:
            self.baseline_result = meter.result()
            self.baseline_result["cpu"] = deepcopy(cpu)
            self.baseline_result["cpuSamples"] = list(meter.route_cpu)
            self.baseline_result["heldFirstThree"] = self.first_three_held
            self.baseline_result["controlBaselinePassed"] = True
            self.baseline_result["nativeTrace"] = deepcopy(list(meter.follower_trace))
            self.baseline_result["lastFollowerTerminal"] = deepcopy(meter.last_follower_terminal)
            self.baseline_result["settledSnapshot"] = deepcopy(meter.latest)

    def arm_args(self, subject, kind):
        if not self.stage("baseline") or not same_subject(subject,self.subject) \
                or self.closed or self.cleanup is not None:
            raise ValueError("route control needs its exact clean baseline")
        if kind not in ("cpu-hitch","player-start-stall") or kind in self.detections \
                or kind == "cpu-hitch" and self.armed_kind is not None \
                or kind == "player-start-stall" and not self.stage("cpu-detected"):
            raise ValueError("route control faults must run once in CPU/player order")
        if not self._settled():
            raise ValueError("route control arm is not a settled boundary")
        select_current_actor(self.latest,self.subject)
        self.armed_kind,self.arm_frame = kind,self.latest["frame"]
        self.arm_cycle = self.latest["nativeCycle"]
        return {"subject":deepcopy(self.subject),"kind":kind,"maxFrames":120}

    def _control(self, value, snapshot, *, closing=False):
        if not isinstance(value,dict) or value.get("type") != "native-route-control-v1" \
                or value.get("kind") != self.armed_kind or not same_subject(value.get("subject"),self.subject) \
                or value.get("failure") is not None or value.get("closed") is not closing:
            raise ValueError("native route control identity/state differs")
        states = ("closed",) if closing else (("cpu-armed","cpu-injected") if self.armed_kind=="cpu-hitch"
                                               else ("player-armed","player-pinning"))
        if value.get("state") not in states:
            raise ValueError("native route control phase differs")
        select_current_actor(snapshot,self.subject)
        rows=value.get("receipts")
        if not isinstance(rows,list) or not len(self.histories)<=len(rows)<=128 \
                or rows[:len(self.histories)] != self.histories:
            raise ValueError("route control receipt history changed")
        for row in rows[len(self.histories):]:
            if not same_subject(row.get("subject"),self.subject) or row.get("context") != snapshot["context"] \
                    or not self.arm_frame<=integer(row.get("frame"))<=snapshot["frame"] \
                    or integer(row.get("nativeCycle"))>snapshot["nativeCycle"]:
                raise ValueError("route control receipt is stale or has another owner")
            binding=(integer(row.get("playerPointer"),0x02000000,0x023FFED4),
                     integer(row.get("playerManager"),0x02000000,0x023FFFFC))
            if any(x&3 for x in binding) or self.owner_binding not in (None,binding):
                raise ValueError("route control player binding changed")
            self.owner_binding=binding
            action=row.get("action")
            if action=="armed":
                if row.get("kind")!=self.armed_kind or row["frame"]!=self.arm_frame \
                        or integer(row.get("maxFrames"),1,120)!=120:
                    raise ValueError("route control arm receipt differs")
                if any(r.get("action")=="armed" and r.get("kind")==row["kind"] for r in self.histories):
                    raise ValueError("duplicate route control arm")
            elif action=="cpu-work":
                if self.armed_kind!="cpu-hitch" or self.cpu_work is not None \
                        or integer(row.get("targetNativeCycle"))!=integer(row.get("nativeCycleBefore"))+1 \
                        or row["nativeCycleBefore"]!=row["nativeCycle"] \
                        or row["targetNativeCycle"]<=self.arm_cycle \
                        or row["targetNativeCycle"]>snapshot["nativeCycle"] \
                        or integer(row.get("workEndCpuNs"))-integer(row.get("workStartCpuNs")) \
                            !=integer(row.get("workCpuNs"),100000000,2000000000):
                    raise ValueError("CPU work receipt is not one measured cycle")
                self.cpu_work=deepcopy(row)
            elif action=="player-admitted":
                if self.armed_kind!="player-start-stall" or self.admission is not None:
                    raise ValueError("unexpected player admission control")
                admission=row.get("admission",{})
                before=admission.get("objectBefore",{})
                if admission.get("objectPointer")!=binding[0] or admission.get("mapId")!=snapshot["context"]["mapId"] \
                        or row.get("pinned")!=[before.get("pos_x"),before.get("pos_z")]:
                    raise ValueError("player control lacks its exact admitted origin")
                self.admission=deepcopy(row)
            elif action=="player-pinned":
                if self.admission is None or self.armed_kind!="player-start-stall" \
                        or row.get("after")!=self.admission["pinned"] \
                        or row.get("writeIndex")!=len(self.pins)+1 \
                        or row["frame"]!=snapshot["frame"] or row["nativeCycle"]!=snapshot["nativeCycle"] \
                        or self.pins and row["frame"]!=self.pins[-1]["frame"]+1:
                    raise ValueError("player pin sequence differs")
                self.pins.append(deepcopy(row))
            elif action=="closed":
                if not closing or row.get("requiresCoreClose") is not True:
                    raise ValueError("player fault cleanup must close the core")
            else:
                raise ValueError("unknown route control receipt")
            self.histories.append(deepcopy(row))

    def _player_detection(self, meter):
        if self.control_failures or self.admission is None or len(self.pins)<4 \
                or "player-start-stall" in self.detections or "cpu-hitch" not in self.detections:
            raise ValueError("player start failure lacks its live pin proof")
        step=meter.step
        receipt=self.admission["admission"]
        if receipt != self.native_admission:
            raise ValueError("player control admission differs from the retained native return")
        if [pin["frame"] for pin in self.pins] != list(range(self.native_admission_frame,meter.control_frame+1)) \
                or len(self.pins)!=sum(sample["accepted"] is True for sample in step["samples"]) \
                or self.pins[-1]["frame"]!=meter.control_frame:
            raise ValueError("player pin frames do not cover the exact admitted samples")
        report=classify_player_motion(step["samples"],step["start"],step["targetRender"],
            maximum_acceptance_frames=2,maximum_start_frames=2,maximum_settle_frames=4)
        if step["callbacks"]!=1 or receipt.get("origin")!=step["origin"] or receipt.get("target")!=step["target"] \
                or report["startStall"]!=1 or report["reachedTarget"] is not False \
                or report["acceptanceStall"] or report["renderRegressions"] or report["interiorStalls"] \
                or any(s["render"]!=self.admission["pinned"] for s in step["samples"]):
            raise ValueError("player failure is not the declared start stall")
        self.detections["player-start-stall"]={"frame":self.pins[-1]["frame"],
            "admissionFrame":self.native_admission_frame,
            "classifier":report,"motion":deepcopy(step),"admission":deepcopy(self.admission),
            "pins":deepcopy(self.pins),"playerMotions":meter.player_motions}

    def observe_record(self, record, *, frame_callback=None, full_report=True):
        if self.closed or self.control_failures or self.baseline.failures:
            return self.result() if full_report else self.progress_result()
        try:
            if self.stage("player-detected"):
                raise ValueError("no gameplay may continue after player fault detection")
            action=self.actions.get((record.get("phase"),record.get("action")))
            if record.get("command")=="observer-control":
                if action is None or action["op"]!="observer-control" or record.get("phase")!="observe":
                    raise ValueError("route control arm is not a sealed action")
                kind=action["args"]["fault"]
                if self.armed_kind!=kind:
                    self.arm_args(self.subject,kind)
                receipt=record["receipt"]; snapshot=record["snapshot"]
                if receipt.get("armed") is not True or receipt.get("frame")!=self.latest["frame"] \
                        or snapshot.get("frame")!=self.latest["frame"] \
                        or any(snapshot.get(k)!=self.latest.get(k) for k in ("nativeCycle","context","player","actors")):
                    raise ValueError("route control arm advanced its boundary")
                self._control(receipt.get("routeControl"),snapshot)
            else:
                if "samples" in record:
                    validate_raw_chunk(record,self.latest)
                    if record.get("phase")=="observe":
                        self.route_cycles.extend(range(self.latest["nativeCycle"]+1,
                                                       self.latest["nativeCycle"]+record["nativeCycles"]+1))
                        if len(self.route_cycles)>self.max_frames*6+120:
                            raise ValueError("route control native interval storage bound exceeded")
                def observed(snapshot,events,meter):
                    self._seal_baseline()
                    if frame_callback: frame_callback(snapshot,events,self)
                    if self.stage("player-detected") and snapshot["frame"]!=record["samples"][-1]["frame"]:
                        raise _EndPlayerFaultChunk("raw chunk continues after the detected player fault")
                self.baseline.observe_record(record,frame_callback=observed,full_report=False)
                if self.baseline_result is not None:
                    self.baseline._cpu_check()
        except (_EndPlayerFaultChunk,ValueError,KeyError,TypeError,IndexError,AttributeError) as error:
            self._fail(error)
        return self.result() if full_report else self.progress_result()

    def observe_cleanup(self, receipt):
        if not self.stage("player-detected") or self.cleanup is not None:
            raise ValueError("route cleanup requires both exact detections once")
        snapshot=receipt["snapshot"]
        if receipt.get("closed") is not True or receipt.get("frame")!=self.latest["frame"] \
                or snapshot["frame"]!=self.latest["frame"] \
                or any(snapshot.get(k)!=self.latest.get(k) for k in ("nativeCycle","context","player","actors")):
            raise ValueError("route cleanup changed the completed frame")
        self._control(receipt.get("routeControl"),snapshot,closing=True)
        if not self.histories or self.histories[-1].get("action")!="closed" \
                or receipt["routeControl"].get("requiresCoreClose") is not True:
            raise ValueError("route cleanup lacks an owned close receipt")
        self.cleanup=deepcopy(receipt)

    def progress_result(self):
        failures=deepcopy(self.control_failures+self.baseline.failures)
        ready=self.stage("complete")
        return {"state":"failed" if failures else "passed" if self.closed and ready else "running",
            "passed":self.closed and ready,"ready":ready,"acceptedProof":False,
            "subject":deepcopy(self.subject),"failures":failures}

    def result(self):
        return {**self.progress_result(),"baseline":deepcopy(self.baseline_result),
            "detections":deepcopy(self.detections),"cleanup":deepcopy(self.cleanup),
            "receipts":deepcopy(self.histories),"observedFrames":self.baseline.observed_frames,
            "scope":"live route recorder calibration only; no normal route frame credit"}

    def finish(self):
        if not self.closed:
            self.baseline._cpu_check()
            if not self.stage("complete"): self._fail("live route controls or cleanup incomplete")
            self.closed=True
        return self.result()
