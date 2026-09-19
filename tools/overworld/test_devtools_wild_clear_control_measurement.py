"""Pure calibration replay; no host fixture is runtime proof."""
from copy import deepcopy
import unittest
from tools.overworld.devtools_wild_clear_control_measurement import WildClearControlMeasurement, KIND
from tools.overworld.test_devtools_wild_walk_measurement import wild_fixture


def fixture(*,startup_noop=False):
    initial,subject,reader,rows=wild_fixture(startup_noop=True) if startup_noop else wild_fixture()
    terminal=deepcopy(rows[-1][0])
    clear=next(e for _,events in rows for e in events if e.get("data",{}).get("observation")=="wild-walk-clear"
               and e["data"]["before"]["active"]==1)
    clean=deepcopy(clear["data"]["after"])
    clean["current"]["publicSubject"]=deepcopy(terminal["actors"][0])
    bad=deepcopy(clean);bad["active"]=1
    clock={k:terminal[k] for k in ("frame","actorFrame","nativeCycle")}
    regs={k:0 for k in (*( "r"+str(i) for i in range(16)),"cpsr","spsr")}
    control=dict(state="complete",failure=None,cleanupPending=False,acceptedProof=False,guestInstructionAdvance=0,
        clean=clean,bad=bad,restored=deepcopy(clean),originalHex="00",changedHex="01",
        stateAddress=clean["current"]["runtimePointer"]+0xA+subject["handle"]["slot"],
        clock=clock,restoredClock=deepcopy(clock),registers=regs,restoredRegisters=deepcopy(regs))
    terminal["wildWalk"].update(guestMemoryWrites=2,clearCalibration=control)
    calibration=dict(phase="observe",command="wild-walk.calibrate",samples=[],events=[],
        receipt=dict(advancedFrames=0,acceptedProof=False,prepared=True,snapshot=deepcopy(terminal),wildWalkControl=control),
        snapshot=deepcopy(terminal))
    final=deepcopy(terminal);final["wildWalk"]["closed"]=True
    close=dict(closed=True,advancedFrames=0,acceptedProof=False,snapshot=final,wildWalk=final["wildWalk"])
    return initial,subject,reader,rows,calibration,close


def replay(fault=None,*,startup_noop=False):
    from tools.overworld.devtools_wild_clear_control_proof import WildClearControlNegative
    initial,subject,reader,rows,calibration,close=fixture(startup_noop=startup_noop)
    meter=WildClearControlMeasurement(1200);meter.arm(subject,initial,reader)
    negative=WildClearControlNegative(fault) if fault else None
    try:
        for snapshot,events in rows:
            row=dict(phase="observe",samples=[snapshot],events=events)
            if negative:row=negative.mutate(row,{"wild":subject})
            meter.observe(row["samples"][0],row["events"])
            if meter.failures:break
        if not meter.failures:
            if negative:calibration=negative.mutate(calibration,{"wild":subject})
            meter.calibrate(calibration["receipt"],calibration["snapshot"])
            meter.close(close,close["snapshot"])
    except (ValueError,KeyError,TypeError) as error:meter.failures.append(str(error))
    result=meter.result()
    return dict(passed=result["passed"],failures=[],measurements={KIND:result})


class WildClearControlMeasurementTests(unittest.TestCase):
    def test_startup_noop_does_not_replace_real_clear(self):
        result=replay(startup_noop=True);meter=result["measurements"][KIND]
        self.assertTrue(result["passed"],meter["failures"])
        self.assertEqual(len(meter["natural"]["idleNoopClears"]),1)
        self.assertEqual(len(meter["natural"]["clearReceipts"]),1)
        self.assertEqual(meter["cleanup"]["wildWalk"]["counts"],{"clear":2})
        self.assertEqual(meter["control"]["clean"]["active"],0)

    def test_wait_natural_walk_then_calibrate(self):
        result=replay();meter=result["measurements"][KIND]
        self.assertTrue(result["passed"],meter["failures"])
        self.assertTrue(meter["natural"]["ready"])
        self.assertFalse(meter["natural"]["passed"])
        self.assertEqual(meter["natural"]["clearReceipts"][0]["data"]["after"]["current"]["publicSubject"]["motionPhase"],"SETTLING")
        self.assertEqual(meter["control"]["clean"]["current"]["publicSubject"]["motionPhase"],"IDLE")

    def test_bad_register_address_and_extra_gameplay_rejected(self):
        for fault in ("register","address","extra-frame"):
            initial,subject,reader,rows,calibration,close=fixture()
            meter=WildClearControlMeasurement(1200);meter.arm(subject,initial,reader)
            for snapshot,events in rows:meter.observe(snapshot,events)
            if fault=="register":calibration["receipt"]["wildWalkControl"]["restoredRegisters"]["r0"]+=1
            elif fault=="address":calibration["receipt"]["wildWalkControl"]["stateAddress"]+=1
            if fault=="extra-frame":
                meter.calibrate(calibration["receipt"],calibration["snapshot"])
                meter.observe(rows[-1][0],[]);self.assertTrue(meter.failures)
            else:
                with self.subTest(fault=fault),self.assertRaises(ValueError):meter.calibrate(calibration["receipt"],calibration["snapshot"])


if __name__=="__main__":unittest.main()
