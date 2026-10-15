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
        self.object_lookups = Counter()
        self.frame_callers = {}
        self.hooks = session.native_observation.hooks
        self.mon_entry = session.packaged_code(0x0206E540, 32)
        if len(self.mon_entry) != 32:
            raise ValueError("native GetMonData code is missing")
        self.mon_token = self.hooks.add(0x0206E540, self._mon_read)
        self.lookup_entries, self.lookup_tokens = {}, []
        for address in (0x0205EE60, 0x0205F214, 0x0205F25C, 0x0205F708,
                        0x0206DD40, 0x0206DD8C, 0x0206EC40, 0x0206E640, 0x0201FF44,
                        0x02054358, 0x02054388, 0x020543BC, 0x020542E8,
                        0x023DEEA2, 0x023DEEBE):
            entry = session.packaged_code(address, 32)
            if len(entry) != 32:
                raise ValueError("native map-object code is missing")
            self.lookup_entries[address] = entry
            self.lookup_tokens.append(self.hooks.add(
                address, lambda address=address: self._lookup_read(address)))
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

    def _lookup_read(self, address):
        if self.closed:
            return
        if self.session.read(address, 32) != self.lookup_entries[address]:
            raise ValueError("native map-object code identity differs")
        regs = self.session.emu.memory.register_arm9
        key = (address, regs.lr & 0xfffffffe)
        if key not in self.object_lookups and len(self.object_lookups) >= 128:
            raise ValueError("CPU work object-lookup bound exceeded")
        self.object_lookups[key] += 1
        frame = self.frame_callers.setdefault(len(self.frames), Counter())
        if key not in frame and len(frame) >= 64:
            raise ValueError("CPU work per-frame caller bound exceeded")
        frame[key] += 1

    def _stop(self):
        self.session.emu.enable_instruction_profile(False)
        self.hooks.remove(self.mon_token)
        for token in self.lookup_tokens:
            self.hooks.remove(token)
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
            allBins=[[address, count] for address, count in self.bins.most_common(4096)],
            monDataReaders=[dict(caller=caller, field=field, calls=count)
                            for (caller, field), count in self.mon_reads.most_common()],
            frameCallers=[[frame, [[function, caller, count]
                                   for (function, caller), count in counter.items()]]
                          for frame, counter in sorted(self.frame_callers.items())],
            objectLookupCallers=[dict(function=function, caller=caller, calls=count)
                                 for (function, caller), count in self.object_lookups.most_common()],
            frames=self.frames, binSize=64, acceptedProof=False,
            scope="ARM9 dispatched instructions, not cycles, elapsed time or a stutter verdict"))
