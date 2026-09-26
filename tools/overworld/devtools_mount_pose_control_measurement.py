"""Idle same-reader calibration witness. Never grants movement credit."""
from copy import deepcopy

from tools.overworld.devtools_records import select_current_actor, engine_binding_identity
from tools.overworld.devtools_mount_pacing_observer import IDENTITY, ENGINE
from tools.overworld.devtools_mount_pacing_measurement import check_pair_pose

KIND = "live-mount-pose-control-v1"


def require(ok, reason):
    if not ok: raise ValueError(reason)


def validate_control(control, pose):
    require(isinstance(control, dict) and control.get("state") == "complete"
        and control.get("failure") is None and control.get("cleanupPending") is False
        and control.get("acceptedProof") is False and type(control.get("guestInstructionAdvance")) is int
        and control["guestInstructionAdvance"] == 0, "mounted pose control is missing or not restored")
    clean, bad, restored = (control[k] for k in ("clean", "bad", "restored"))
    require(all(clean.get(k) == pose.get(k) for k in ("subject", "publicSubject", "sourceIdentity",
        "engineIdentity", "worldContext", "playerPointer", "mountPointer", "avatarPointer",
        "player", "mount", "avatarControl")), "mounted pose control differs from its completed sample")
    check_pair_pose(clean)
    expected = deepcopy(clean);expected["mount"]["pos_x"] += 1
    require(bad == expected and restored == clean, "mounted pose fault or restoration differs")
    try:
        check_pair_pose(bad)
    except ValueError:
        pass
    else:
        raise ValueError("mounted pose bad data passed the unchanged checker")
    address = clean["mountPointer"] + 0x70
    require(type(control.get("poseAddress")) is int and control["poseAddress"] == address
        and address % 4 == 0 and 0x02000000 <= address <= 0x023FFFFC
        and control.get("originalHex") == clean["mount"]["pos_x"].to_bytes(4,"little",signed=True).hex()
        and control.get("changedHex") == bad["mount"]["pos_x"].to_bytes(4,"little",signed=True).hex(),
        "mounted pose control bytes or address differ")
    clock = control.get("clock", {})
    require(set(clock) == {"frame", "actorFrame", "nativeCycle"}
        and all(type(v) is int and v >= 0 for v in clock.values())
        and clock == control.get("restoredClock") and clock["frame"] == pose["frame"]
        and clock["actorFrame"] == pose["actorFrame"] and clock["nativeCycle"] >= pose["nativeCycle"],
        "mounted pose control clocks differ")
    registers = control.get("registers", {})
    require(set(registers) == {*('r'+str(i) for i in range(16)), 'cpsr', 'spsr'}
        and control.get('restoredRegisters') == registers
        and all(type(v) is int and 0 <= v <= 0xFFFFFFFF for v in registers.values()),
        "mounted pose control register receipt differs")
    if clean.get("gait") is not None:
        require(clean["gait"] == pose.get("gait"),
                "mounted gait control differs from its completed capsule or inputs")
        paused = clean.get("pausedGaitClock")
        if paused is not None:
            require(set(paused) == {"completedStamp", "nativeStamp", "completedFrame",
                    "completedActorFrame", "completedNativeCycle", "pausedNativeCycle"}
                and all(type(v) is int and v >= 0 for v in paused.values())
                and paused["completedStamp"] == pose["gait"]["input"]["stamp"]
                and paused["nativeStamp"] <= 0xFFFFFFFF
                and ((paused["nativeStamp"] - paused["completedStamp"]) & 0xFFFFFFFF) in (1, 2)
                and paused["completedFrame"] == pose["frame"]
                and paused["completedActorFrame"] == pose["actorFrame"]
                and paused["completedNativeCycle"] == pose["nativeCycle"]
                and paused["pausedNativeCycle"] == clock["nativeCycle"],
                "mounted gait paused clock is not bound to the completed sample")
            raw = deepcopy(clean)
            del raw["pausedGaitClock"]
            raw["gait"]["input"]["stamp"] = paused["nativeStamp"]
            require(control.get("latestRawPose") == raw,
                    "mounted gait paused raw reader receipt differs")
        gait_control = control.get("gaitOffsetControl", {})
        expected = deepcopy(clean)
        expected["mount"]["unk88_y"] += 1
        require(gait_control.get("clean") == clean and gait_control.get("bad") == expected
                and gait_control.get("restored") == clean
                and gait_control.get("address") == clean["mountPointer"] + 0x8C
                and gait_control.get("originalHex") == clean["mount"]["unk88_y"].to_bytes(2, "little", signed=True).hex()
                and gait_control.get("changedHex") == expected["mount"]["unk88_y"].to_bytes(2, "little", signed=True).hex()
                and gait_control.get("clock") == clock
                and gait_control.get("restoredClock") == clock,
                "mounted gait same-reader offset fault or restoration differs")
        try:
            check_pair_pose(gait_control["bad"])
        except ValueError:
            pass
        else:
            raise ValueError("mounted gait native offset fault passed the checker")


class MountedPoseControlMeasurement:
    def __init__(self, *, max_frames):
        require(type(max_frames) is int and 1 <= max_frames <= 1200, "invalid mounted pose control bound")
        self.maximum=max_frames
        self.initial=self.latest=self.subject=self.control=self.cleanup=None
        self.frames=0;self.closed=False;self.failures=[]

    def _actor(self, snapshot):
        selected=select_current_actor(snapshot,self.subject)
        actor=next(a for a in snapshot['actors'] if a['handle']==selected['handle'])
        require(snapshot['context']==self.initial['context'] and all(actor.get(k)==self.actor.get(k)
            for k in (*IDENTITY,'sourceIdentity','commitSequence','logical'))
            and engine_binding_identity(actor['engineIdentity'])==engine_binding_identity(self.actor['engineIdentity'])
            and actor['motionPhase']=='IDLE' and actor['motionKind']=='NONE'
            and actor['reservationId']==0 and actor['inputOwnership']==1,
            'mounted pose control owner moved or changed')
        return actor

    def _reader(self, value, closed):
        require(value.get('armed') is True and value.get('closed') is closed
            and value.get('failure') is None and value.get('acceptedProof') is False
            and value.get('subject')==self.subject and value.get('startFrame')==self.initial['frame']
            and value.get('guestMemoryWrites')==((4 if self.control.get('gaitOffsetControl') else 2) if self.control else 0)
            and value.get('poseCalibration')==self.control, 'mounted pose reader state differs')

    def arm(self, subject, snapshot, receipt, trace_sequences=None):
        require(self.initial is None and receipt.get('armed') is True and receipt.get('prepared') is True
            and receipt.get('acceptedProof') is False and receipt.get('snapshot')==snapshot
            and snapshot.get('prepared') is True, 'mounted pose arm endpoint differs')
        self.subject=select_current_actor(snapshot,subject)
        require(self.subject==subject and subject['species']==155 and subject['role']=='MOUNTED',
                'mounted pose control requires current Cyndaquil')
        self.initial=deepcopy(snapshot)
        self.actor=deepcopy(next(a for a in snapshot['actors'] if a['handle']==subject['handle']))
        self._actor(snapshot);self._reader(receipt['mountPacing'],False)
        require(receipt['mountPacing']['counts']=={'presentation':0,'playerStep':0}, 'mounted pose reader was already used')
        self.latest=deepcopy(snapshot)

    def observe(self, snapshot, events):
        try:
            require(self.initial is not None and not self.closed and self.control is None,
                    'mounted pose sample is outside idle calibration setup')
            require(snapshot['frame']==self.latest['frame']+1 and snapshot['nativeCycle']>=self.latest['nativeCycle']
                and snapshot.get('observationBoundary')=='main-task-queue-completion'
                and snapshot.get('prepared') is True, 'mounted pose completed clock differs')
            actor=self._actor(snapshot);self._reader(snapshot['mountPacing'],False)
            pose=snapshot['mountPacing']['latestCompletedPose']
            require(pose['boundary']=='main-task-queue-completion' and all(pose[k]==snapshot[k]
                for k in ('frame','nativeCycle','actorFrame')) and pose['subject']==self.subject
                and all(pose['worldContext'].get(k)==snapshot['context'].get(k)
                        for k in ('fieldEpoch','mapGeneration','mapId'))
                and all(type(pose['worldContext'].get(k)) is int
                        and 0x02000000 <= pose['worldContext'][k] < 0x02400000
                        and pose['worldContext'][k] % 4 == 0 for k in ('fieldPointer','statePointer'))
                and all(pose['publicSubject'].get(k)==actor.get(k) for k in (*IDENTITY,
                    'motionPhase','motionKind','reservationId','commitSequence','logical'))
                and pose['sourceIdentity']==actor['sourceIdentity']
                and all(pose['engineIdentity'].get(k)==actor['engineIdentity'].get(k) for k in ENGINE)
                and pose['mountPointer']==actor['engineIdentity']['pointer']
                and pose['playerPointer']==actor['engineIdentity']['anchorPointer'], 'mounted pose completed binding differs')
            check_pair_pose(pose)
            native=snapshot['nativeObservation']
            require(native.get('installedBeforeBoot') is True and native.get('coverageComplete') is True
                and native.get('eventsDropped')==0 and native.get('profilesEvicted')==0
                and native.get('pendingUnframedEvents')==0 and native.get('error') is None,
                'mounted pose native coverage differs')
            require(not any(e.get('kind')=='native' and e.get('data',{}).get('actorHandle')==actor['handle']['value']
                and e['data'].get('event') in ('MOTION_STARTED','LOGICAL_COMMIT','MOTION_FINISHED','CONTROL_RETURNED','MOTION_CANCELED')
                for e in events), 'mounted pose control window contains movement')
            self.frames+=1
            require(self.frames<=self.maximum,'mounted pose frame budget exceeded')
            self.latest=deepcopy(snapshot)
        except (ValueError,KeyError,TypeError,IndexError) as error:
            self.failures.append(dict(detail=str(error),code='mounted-pose-control-invalid'))
        return self.result()

    def calibrate(self, receipt, snapshot):
        require(self.frames>=1 and not self.failures and self.control is None and not self.closed
            and receipt.get('advancedFrames')==0 and receipt.get('acceptedProof') is False
            and receipt.get('prepared') is True and receipt.get('snapshot')==snapshot,
            'mounted pose calibration lacks its completed sample')
        self._actor(snapshot)
        control=receipt.get('mountedPoseControl')
        validate_control(control,self.latest['mountPacing']['latestCompletedPose'])
        self.control=deepcopy(control)
        self._reader(snapshot['mountPacing'],False)

    @property
    def ready(self):return self.frames>=1 and self.control is not None and not self.failures

    def close(self, receipt, snapshot):
        require(self.ready and not self.closed and receipt.get('closed') is True
            and receipt.get('advancedFrames')==0 and receipt.get('acceptedProof') is False
            and all(receipt.get('snapshot',{}).get(k)==snapshot.get(k) for k in
                ('frame','nativeCycle','actorFrame','context','player','actors','nativeObservation')),
            'mounted pose reader cleanup missing')
        self._actor(snapshot);self._reader(receipt['mountPacing'],True)
        require(receipt['mountPacing']['latestCompletedPose']==self.latest['mountPacing']['latestCompletedPose'],
                'mounted pose cleanup sample changed')
        self.closed=True;self.cleanup=deepcopy(receipt)

    def result(self):
        return deepcopy(dict(kind=KIND,ready=self.ready,passed=self.ready and self.closed,acceptedProof=False,
            subject=self.subject,observedFrames=self.frames,failures=self.failures,control=self.control,
            pose=self.latest.get('mountPacing',{}).get('latestCompletedPose') if self.latest else None,cleanup=self.cleanup))

    def finish(self):
        if not self.ready or not self.closed:self.failures.append(dict(detail='mounted pose control incomplete'))
        return self.result()
