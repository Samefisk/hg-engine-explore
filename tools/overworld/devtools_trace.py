"""Bounded public semantic-trace tap for diagnostic development recordings.

Call start/stop while the emulator is paused. Publish at completed game frames.
The authenticated native writer-return tap can drain half-full rings into a
pending host buffer; those records do not become coherent frame samples early.
Only decoded ROM records have kind='native'. Observer notices use the distinct
kind='trace-status'; they are not invented gameplay events or proof receipts.
"""
from __future__ import annotations

from copy import deepcopy

from tools.overworld.actor_probe import configure_runtime_trace, finish_runtime_trace
from tools.overworld.trace import HEADER, RECORD, TRACE_VERSION, decode_trace_bytes
from tools.overworld.validation import ValidationFailure


def _integer(value, label, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{label} must be an integer in {low}..{high}")
    return value


class SemanticTrace:
    def __init__(self, read, write, descriptor, schema):
        if not callable(read) or not callable(write):
            raise ValueError("trace needs public memory read/write transports")
        self.read, self.write = read, write
        self.descriptor, self.schema = deepcopy(descriptor), deepcopy(schema)
        try:
            state = descriptor["state"]
            self.capacity = _integer(descriptor["capacities"]["traceEvents"], "trace capacity", 1, 128)
            _integer(descriptor["capacities"]["actors"], "actor capacity", 1, 65535)
            if self.capacity & (self.capacity - 1):
                raise ValueError("trace capacity must be a power of two")
            if descriptor["structures"]["traceHeader"] != HEADER.size or descriptor["structures"]["traceEvent"] != RECORD.size:
                raise ValueError("descriptor trace layout differs from the public decoder")
            address = _integer(state["address"], "state address", 0x02000000, 0x023FFFFF)
            self.header_address = address + _integer(state["offsets"]["traceHeader"], "trace header offset", 0, 0x3FFFFF)
            self.events_address = address + _integer(state["offsets"]["traceEvents"], "trace event offset", 0, 0x3FFFFF)
            if self.header_address + HEADER.size > 0x02400000 or self.events_address + self.capacity * RECORD.size > 0x02400000:
                raise ValueError("public trace exceeds main RAM")
            if not (self.header_address + HEADER.size <= self.events_address
                    or self.events_address + self.capacity * RECORD.size <= self.header_address):
                raise ValueError("trace header overlaps its event ring")
            if schema["schemaVersion"] != TRACE_VERSION or schema["magic"] != "OWTR" \
                    or schema["header"] != {"format": HEADER.format, "size": HEADER.size} \
                    or schema["record"] != {"format": RECORD.format, "size": RECORD.size}:
                raise ValueError("generated trace schema differs from the public decoder")
        except (KeyError, TypeError) as error:
            raise ValueError("trace descriptor/schema is incomplete") from error
        self.running = False
        self.stream = 0
        self._next = 1
        self._header = None
        self._seen = {}
        self._pending = []
        self._ended = False
        self._last_fault = None

    def _read_exact(self, address, size):
        data = self.read(address, size)
        if not isinstance(data, (bytes, bytearray)) or len(data) != size:
            raise ValidationFailure("public trace read returned the wrong byte count")
        return bytes(data)

    def _capture(self):
        before = self._read_exact(self.header_address, HEADER.size)
        records = self._read_exact(self.events_address, RECORD.size * self.capacity)
        after = self._read_exact(self.header_address, HEADER.size)
        if before != after:
            raise ValidationFailure("trace header changed during its paused observation")
        decoded = decode_trace_bytes(before + records, self.schema, self.capacity)
        header = decoded["header"]
        if header["writeIndex"] >= self.capacity or header["armed"] not in (0, 1):
            raise ValidationFailure("native trace index/armed flag is invalid")
        if header["oldestSequence"] < 1 or header["nextSequence"] < 1 \
                or header["nextSequence"] - header["oldestSequence"] != header["count"]:
            raise ValidationFailure("native trace sequence range differs from its record count")
        if [event["sequence"] for event in decoded["events"]] != list(range(header["oldestSequence"], header["nextSequence"])):
            raise ValidationFailure("native trace has duplicate or missing sequence records")
        return decoded

    def start(self, frame_limit=1800):
        """Reset and arm one explicit 1..65535-actor-frame diagnostic window.

        No automatic rearm hides expired coverage. Stop then start to open a
        new window; the next sample reports that restart and any unread tail.
        """
        _integer(frame_limit, "trace frame limit", 1, 65535)
        if self.running:
            raise ValueError("this trace window is already running")
        before = self._capture()["header"]
        if before["armed"]:
            raise ValueError("another trace is armed; do not clear its records")
        discarded = max(0, before["nextSequence"] - self._next) if self.stream else 0
        configure_runtime_trace(self.read, self.write, self.descriptor,
                                event_mask=0, frame_budget=frame_limit)
        current = self._capture()["header"]
        if current["armed"] != 1 or current["count"] != 0 or current["nextSequence"] != 1:
            raise ValidationFailure("native trace did not accept the requested window")
        self.stream += 1
        self.running = True
        self._next, self._seen, self._header = 1, {}, current
        self._ended, self._last_fault = False, None
        self._pending = [{"code": "window-started" if self.stream == 1 else "window-restarted",
                          "frameLimit": frame_limit, "clock": "actor-system-frames",
                          "discardedUnreadBeforeRestart": discarded}]

    def _notice(self, game_frame, code, **details):
        return {"frame": game_frame, "kind": "trace-status", "data": {
            "code": code, "traceStream": self.stream,
            "diagnosticOnly": True, **details}}

    def capture_publication(self):
        """Drain before a busy frame can overwrite unread records.

        Called only after the native writer has returned. A cheap counter read
        batches at half the fixed ring capacity; the existing strict decoder
        still checks full records, loss, resets and filter changes. Frame zero
        is private pending data and must be stamped only at queue completion.
        """
        if not self.running:
            return []
        next_sequence = int.from_bytes(self._read_exact(self.header_address + 12, 4), "little")
        if next_sequence >= self._next and next_sequence - self._next < max(1, self.capacity // 2):
            return []
        return self.sample(0)

    def sample(self, game_frame):
        _integer(game_frame, "game frame", 0, 0xFFFFFFFF)
        if self.stream == 0:
            raise ValueError("start the trace before sampling")
        result = [self._notice(game_frame, **notice) for notice in self._pending]
        self._pending = []
        try:
            decoded = self._capture()
        except (ValueError, ValidationFailure) as error:
            message = str(error)
            if message != self._last_fault:
                result.append(self._notice(game_frame, "invalid-native-ring", message=message,
                                           coverageComplete=False))
            self._last_fault = message
            return result
        if self._last_fault is not None:
            result.append(self._notice(game_frame, "read-recovered", coverageComplete=False))
            self._last_fault = None
        header, events = decoded["header"], decoded["events"]
        previous = self._header
        changed_old_records = any(event["sequence"] in self._seen and self._seen[event["sequence"]] != event for event in events)
        reset = (header["nextSequence"] < self._next
                 or header["oldestSequence"] < previous["oldestSequence"]
                 or header["overwrittenCount"] < previous["overwrittenCount"]
                 or changed_old_records)
        if reset:
            old_stream = self.stream
            self.stream += 1
            result.append(self._notice(game_frame, "sequence-reset", previousStream=old_stream,
                                       previousNext=self._next, currentNext=header["nextSequence"],
                                       sequenceReused=changed_old_records, coverageComplete=False))
            self._next, self._seen = 1, {}
            self._ended = False
        if header["fieldEpoch"] != previous["fieldEpoch"]:
            result.append(self._notice(game_frame, "field-epoch-changed",
                                       previousEpoch=previous["fieldEpoch"], fieldEpoch=header["fieldEpoch"],
                                       sequenceReset=reset))
        lost = max(0, header["oldestSequence"] - self._next)
        if lost:
            result.append(self._notice(game_frame, "unread-events-lost", count=lost,
                                       firstMissingSequence=self._next,
                                       lastMissingSequence=header["oldestSequence"] - 1,
                                       coverageComplete=False))
        overwritten = header["overwrittenCount"] - (0 if reset else previous["overwrittenCount"])
        if overwritten > 0:
            result.append(self._notice(game_frame, "ring-overwrite", count=overwritten,
                                       unreadEventsLost=lost))
        for event in events:
            if event["sequence"] < self._next:
                continue
            result.append({"frame": game_frame, "kind": "native", "data": {
                **deepcopy(event), "actorFrame": event["frame"],
                "traceStream": self.stream, "traceFieldEpoch": header["fieldEpoch"]}})
        self._next = header["nextSequence"]
        self._seen = {event["sequence"]: deepcopy(event) for event in events}
        self._header = header
        if not header["armed"] and not self._ended:
            result.append(self._notice(game_frame, "window-ended",
                                       reason="stopped" if not self.running else "budget-expired-or-disarmed",
                                       frameLimitRemaining=header["filterFramesRemaining"]))
            self._ended = True
        if header["armed"] and not previous["armed"]:
            result.append(self._notice(game_frame, "window-rearmed-externally", coverageComplete=False))
            self._ended = False
        changed_filter = (header["filterEventMask"] != previous["filterEventMask"]
                          or header["filterActor"] != previous["filterActor"])
        if changed_filter:
            result.append(self._notice(game_frame, "trace-filter-changed", coverageComplete=False,
                                       filterEventMask=header["filterEventMask"], filterActor=header["filterActor"]))
        return result

    def stop(self):
        """Disable public instrumentation only; retained events remain readable."""
        if self.stream == 0 or not self.running:
            return
        finish_runtime_trace(self.read, self.write, self.descriptor)
        self.running = False
