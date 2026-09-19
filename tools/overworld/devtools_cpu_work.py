"""Bounded host-only CPU work diagnostics through the shared native core.

Counts dispatches, not elapsed time. Raw PC bins can cross function boundaries;
symbol names are an investigation aid, never automatic ownership proof.
"""
from collections import Counter
from copy import deepcopy


class CPUWorkProbe:
    def __init__(self, session, maximum):
        if type(maximum) is not int or not 1 <= maximum <= 1200:
            raise ValueError("CPU work probe requires 1..1200 native frames")
        if not session.prepared or getattr(session, "cpu_work_probe", None) is not None:
            raise ValueError("CPU work probe requires fresh prepared diagnostic scope")
        self.session, self.maximum = session, maximum
        self.frames, self.bins = [], Counter()
        self.closed, self.failure = False, None
        self.total = self.unmapped = 0
        self.last = None
        self.mon_reads = Counter()
        self.hooks = session.native_observation.hooks
        self.mon_entry = session.packaged_code(0x0206E540, 32)
        if len(self.mon_entry) != 32:
            raise ValueError("native GetMonData code is missing")
        self.mon_token = self.hooks.add(0x0206E540, self._mon_read)
        session.emu.enable_instruction_profile(True)
        session.cpu_work_probe = self

    def _mon_read(self):
        if self.closed:
            return
        if self.session.read(0x0206E540, 32) != self.mon_entry:
            raise ValueError("native GetMonData code identity differs")
        regs = self.session.emu.memory.register_arm9
        key = (regs.lr & 0xfffffffe, regs.r1 & 0xffffffff)
        if key not in self.mon_reads and len(self.mon_reads) >= 128:
            raise ValueError("CPU work mon-reader bound exceeded")
        self.mon_reads[key] += 1

    def _stop(self):
        self.session.emu.enable_instruction_profile(False)
        self.hooks.remove(self.mon_token)
        self.closed = True

    def observe_cycle(self):
        if self.closed:
            return
        try:
            row = self.session.emu.instruction_profile()
            if not row["enabled"] or not row["complete"]:
                raise ValueError("CPU work native frame is incomplete")
            if self.last is not None and row["frameSequence"] != self.last + 1:
                raise ValueError("CPU work native frame sequence differs")
            self.last = row["frameSequence"]
            self.total += row["total"]
            self.unmapped += row["unmapped"]
            self.bins.update(dict(row["bins"]))
            self.frames.append(dict(nativeFrame=row["frameSequence"],
                afterQueueFrame=self.session.completed_frames,
                total=row["total"], unmapped=row["unmapped"],
                topBins=sorted(row["bins"], key=lambda item: (-item[1], item[0]))[:16]))
            if len(self.frames) == self.maximum:
                self._stop()
        except Exception as error:
            self.failure = str(error)
            self._stop()
            raise

    def result(self):
        return deepcopy(dict(schemaVersion=1, maxNativeFrames=self.maximum,
            observedNativeFrames=len(self.frames), closed=self.closed, failure=self.failure,
            total=self.total, unmapped=self.unmapped,
            topBins=[[address, count] for address, count in self.bins.most_common(48)],
            monDataReaders=[dict(caller=caller, field=field, calls=count)
                            for (caller, field), count in self.mon_reads.most_common()],
            frames=self.frames, binSize=64, acceptedProof=False,
            scope="ARM9 dispatched instructions, not cycles, elapsed time or a stutter verdict"))
