"""Same-reader clear calibration after one proven natural Wild Walk.

The normal movement reducer remains write-free. Calibration is a separate
terminal phase and supplies recorder evidence, never natural movement credit.
"""
from copy import deepcopy
from tools.overworld.devtools_wild_walk_measurement import WildWalkMeasurement, IDENTITY
from tools.overworld.devtools_wild_walk_observer import check_cleared_state, RUNTIME_ACTIVE

KIND = "live-wild-clear-control-v1"


def require(value, reason):
    if not value: raise ValueError(reason)


def validate_control(control, clear, terminal):
    require(isinstance(control,dict) and control.get("state")=="complete" and control.get("failure") is None
        and control.get("cleanupPending") is False and control.get("acceptedProof") is False
        and type(control.get("guestInstructionAdvance")) is int and control["guestInstructionAdvance"]==0,
        "Wild clear control is missing or not restored")
    clean,bad,restored=(control[k] for k in ("clean","bad","restored"))
    current=clean["current"]
    prior=clear["data"] if "data" in clear else clear
    require(prior["before"].get("active")==1 and prior["before"].get("mode")==1,
            "Wild clear control lacks real Walk clear")
    check_cleared_state(prior["after"]);check_cleared_state(clean)
    require(all(current.get(k)==prior["after"]["current"].get(k) for k in
        ("subject","sourceIdentity","engineIdentity","worldContext","statePointer","runtimePointer","objectPointer","slot")),
        "Wild clear control owner differs")
    actor=next(a for a in terminal["actors"] if a["handle"]==current["subject"]["handle"])
    require(all(current["publicSubject"].get(k)==actor.get(k) for k in (*IDENTITY,"motionKind","motionPhase",
                "commitSequence","logical","reservationId")) and actor["motionKind"]=="NONE"
                and actor["motionPhase"]=="IDLE" and actor["reservationId"]==0,
            "Wild clear control terminal owner differs")
    expected=deepcopy(clean);expected["active"]=1
    require(bad==expected and restored==clean,"Wild clear fault or restoration differs")
    try:check_cleared_state(bad)
    except ValueError:pass
    else:raise ValueError("Wild clear bad data passed unchanged checker")
    address=current["runtimePointer"]+RUNTIME_ACTIVE+current["slot"]
    require(type(control.get("stateAddress")) is int and control["stateAddress"]==address
            and 0x02000000<=address<0x02400000 and control.get("originalHex")=="00"
            and control.get("changedHex")=="01","Wild clear control bytes or address differ")
    clock=control.get("clock",{})
    require(set(clock)=={"frame","actorFrame","nativeCycle"} and all(type(v) is int and v>=0 for v in clock.values())
        and clock==control.get("restoredClock") and clock["frame"]==terminal["frame"]
        and clock["actorFrame"]==terminal["actorFrame"] and clock["nativeCycle"]>=terminal["nativeCycle"],
        "Wild clear control clocks differ")
    registers=control.get("registers",{})
    require(set(registers)=={*("r"+str(i) for i in range(16)),"cpsr","spsr"}
        and registers==control.get("restoredRegisters")
        and all(type(v) is int and 0<=v<=0xFFFFFFFF for v in registers.values()),
        "Wild clear control registers differ")


class WildClearControlMeasurement:
    def __init__(self,max_frames):
        self.natural=WildWalkMeasurement(max_frames)
        self.control=self.cleanup=None
        self.closed=False;self.failures=[]

    @property
    def initial(self):return self.natural.initial
    @property
    def frames(self):return self.natural.frames
    @property
    def ready(self):return self.natural.ready and self.control is not None and not self.failures

    def arm(self,subject,snapshot,receipt,trace_sequences=None):
        self.natural.arm(subject,snapshot,receipt,trace_sequences)

    def observe(self,snapshot,events):
        if self.failures:return self.result()
        if self.closed or self.control is not None:
            self.failures.append("Wild clear control observed gameplay after calibration")
        else:
            self.natural.observe(snapshot,events)
            self.failures=list(self.natural.failures)
        return self.result()

    def stage(self,name):
        return name=="natural-walk-complete" and self.natural.ready and not self.failures

    def calibrate(self,receipt,snapshot):
        require(self.natural.ready and not self.failures and self.control is None and not self.closed
            and receipt.get("advancedFrames")==0 and receipt.get("acceptedProof") is False
            and receipt.get("prepared") is True and receipt.get("snapshot")==snapshot,
            "Wild clear calibration lacks completed natural Walk")
        self.natural._actor(snapshot)
        require(all(snapshot.get(k)==self.natural.last.get(k) for k in
            ("frame","actorFrame","actors","context","player")),"Wild clear calibration moved its terminal endpoint")
        control=receipt.get("wildWalkControl")
        validate_control(control,self.natural.clears[-1],self.natural.last)
        self._reader(snapshot["wildWalk"],False,control)
        self.control=deepcopy(control)

    def _reader(self,value,closed,control):
        expected_clears=len(self.natural.clears)+len(self.natural.result().get("idleNoopClears",[]))
        require(value.get("armed") is True and value.get("closed") is closed and value.get("failure") is None
            and value.get("subject")==self.natural.subject and value.get("startFrame")==self.initial["frame"]
            and value.get("counts")=={"clear":expected_clears} and value.get("guestMemoryWrites")==2
            and value.get("acceptedProof") is False and value.get("clearCalibration")==control,
            "Wild clear calibrated reader differs")

    def close(self,receipt,snapshot):
        require(self.ready and not self.closed and receipt.get("closed") is True and receipt.get("advancedFrames")==0
            and receipt.get("acceptedProof") is False
            and all(receipt.get("snapshot",{}).get(k)==snapshot.get(k) for k in
                    ("frame","nativeCycle","actorFrame","context","actors","player"))
            and {k:v for k,v in receipt.get("snapshot",{}).get("nativeObservation",{}).items() if k!="resolvedProfiles"}
                == {k:v for k,v in snapshot.get("nativeObservation",{}).items() if k!="resolvedProfiles"},
            "Wild clear calibration cleanup missing")
        self.natural._actor(snapshot)
        require(all(snapshot.get(k)==self.natural.last.get(k) for k in
            ("frame","actorFrame","actors","context","player")),"Wild clear cleanup moved terminal endpoint")
        self._reader(receipt["wildWalk"],True,self.control)
        self.closed=True;self.cleanup=deepcopy(receipt)
        return self.result()

    def finish(self):
        if not self.ready or not self.closed:self.failures.append("Wild clear control incomplete")
        return self.result()

    def result(self):
        return deepcopy(dict(kind=KIND,ready=self.ready,passed=self.ready and self.closed,acceptedProof=False,
            closed=self.closed,subject=getattr(self.natural,"subject",None),observedFrames=self.frames,
            failures=self.failures,control=self.control,cleanup=self.cleanup,
            terminal=self.natural.last,natural=self.natural.result()))
