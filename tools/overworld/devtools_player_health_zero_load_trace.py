"""Bounded read-only blackout history at the completed main-queue boundary."""

import struct


class ZeroLoadRecoveryTrace:
    LIMIT = 4096

    def __init__(self, code, data):
        self.code = code
        self.data = data
        self.root = code["PlayerHealthRecovery_BlackoutTask"][0] | 1
        self.stock = code["PlayerHealthRecovery_StockBlackoutTask"][0] | 1
        self.history = []
        self.overlay_reads = {(address, size) for address, size, _ in code.values()}
        self.overlay_reads.add((data["sBlackoutFieldSystem"][0], 4))
        self.overlay_reads.add((data["sBlackoutFailed"][0], 1))

    @staticmethod
    def _pointer(value, size=4):
        if type(value) is not int or value & 3 or not 0x02000000 <= value <= 0x02400000 - size:
            raise ValueError("zero-load task pointer is invalid")
        return value

    def observe(self, read, field, frame, cycle, *, read_overlay=None):
        def checked_read(address, size):
            # The recovery overlay is mapped below main RAM. Only exact spans
            # authenticated by _zero_hp_boot_layout may use the overlay reader.
            reader = (read_overlay or read) if (address, size) in self.overlay_reads else read
            value = reader(address, size)
            if not isinstance(value, (bytes, bytearray)) or len(value) != size:
                raise ValueError("zero-load trace has a short native read")
            return value
        if len(self.history) >= self.LIMIT:
            raise ValueError("zero-load recovery trace is too long")
        if type(frame) is not int or type(cycle) is not int or frame != len(self.history) + 1:
            raise ValueError("zero-load recovery trace skips a queue")
        row = {"frame": frame, "nativeCycle": cycle, "field": field,
               "root": None, "stock": None, "messageInputReady": False}
        if field:
            self._pointer(field, 0x70)
            task = struct.unpack("<I", checked_read(field + 0x10, 4))[0]
            chain, seen = [], set()
            while task:
                self._pointer(task, 32)
                if task in seen or len(chain) >= 8:
                    raise ValueError("zero-load task chain is cyclic or too deep")
                seen.add(task)
                previous, callback, state, env, _, _, owner, _ = struct.unpack(
                    "<8I", checked_read(task, 32))
                if owner != field:
                    raise ValueError("zero-load task owner differs")
                chain.append((task, callback, state, env))
                task = previous
            roots = [item for item in chain if item[1] == self.root]
            stocks = [item for item in chain if item[1] == self.stock]
            if len(roots) > 1 or len(stocks) > 1:
                raise ValueError("zero-load recovery task is duplicated")
            if roots:
                if chain[-1] != roots[0] or not 0 <= roots[0][2] <= 2:
                    raise ValueError("zero-load root task state or place differs")
                for name in ("PlayerHealthRecovery_BlackoutTask",
                             "PlayerHealthRecovery_StockBlackoutTask"):
                    address, size, expected = self.code[name]
                    if checked_read(address, size) != expected:
                        raise ValueError("zero-load live recovery code differs")
                owner_addr = self.data["sBlackoutFieldSystem"][0]
                if struct.unpack("<I", checked_read(owner_addr, 4))[0] != field:
                    raise ValueError("zero-load recovery field owner differs")
                if checked_read(self.data["sBlackoutFailed"][0], 1) != b"\0":
                    raise ValueError("zero-load recovery failure flag is set")
                row["root"] = {"pointer": roots[0][0], "state": roots[0][2]}
            if stocks:
                if not roots or len(chain) < 2 or chain[-2] != stocks[0] \
                        or not 0 <= stocks[0][2] <= 6:
                    raise ValueError("zero-load stock task has no current root")
                row["stock"] = {"pointer": stocks[0][0], "state": stocks[0][2]}
                if stocks[0][2] == 4 and len(chain) >= 3 and chain[-3] == chain[0]:
                    # In stock blackout state DRAW, its only child is the
                    # printed-message task. Its environment byte is the
                    # source-defined input-wait state (2).
                    child = chain[0]
                    if child[1] & 1 == 0 or not 0x02000001 <= child[1] < 0x02400000:
                        raise ValueError("zero-load message callback is invalid")
                    self._pointer(child[3], 1)
                    row["messageInputReady"] = checked_read(child[3], 1) == b"\2"
        self.history.append(row)
        return row
