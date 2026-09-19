"""Bounded stationary stock-player waits, justified by native collision reads.

The caller authenticates the stock collision callback and merges its outer
completed frame into each receipt. A true result excludes this frame from
movement credit; it does not mark the requested step complete.
"""
from copy import deepcopy

DIRECTIONS = {"UP": (0, -1, 0, 64), "DOWN": (0, 1, 1, 128),
              "LEFT": (-1, 0, 2, 32), "RIGHT": (1, 0, 3, 16)}
CONTEXT = ("mapId", "fieldEpoch", "mapGeneration")
MAX_WAIT_FRAMES = 120
# Stock unk_02062108.s: Cmd028..031 pass 0x10 to sub_020627B0,
# which stores 17; Cmd040_Step1 decrements to zero. Permit that complete
# 17-frame bump plus the next poll. Missing reads cannot start a wait.
MAX_RECEIPT_GAP = 18


def require(ok, why):
    if not ok:
        raise ValueError("player collision wait: " + why)


def integer(value, low=0, high=0xFFFFFFFF):
    require(type(value) is int and low <= value <= high, "invalid integer")
    return value


def context(value):
    return {k: integer(value[k]) for k in CONTEXT}


def tile(value):
    return [integer(value[k], 0, 32767) for k in ("x", "y")]


def pose(value):
    return [integer(value[k], -0x80000000, 0x7FFFFFFF) for k in ("pos_x", "pos_z")]


class PlayerCollisionWait:
    def __init__(self):
        self.proofs = []
        self.active = None
        self.failure = None

    @property
    def ready(self):
        return self.failure is None and self.active is None

    def observe(self, snapshot, step, receipts, admitted=False):
        if self.failure is not None:
            raise ValueError(self.failure)
        try:
            return self._observe(snapshot, step, receipts, admitted)
        except (ValueError, KeyError, TypeError, IndexError, AttributeError) as error:
            self.failure = str(error)
            raise ValueError("player collision wait invalid: " + str(error)) from error

    def _observe(self, snapshot, step, receipts, admitted):
        require(type(admitted) is bool and isinstance(receipts, list) and len(receipts) <= 1,
                "multiple or invalid collision receipts")
        if not receipts and self.active is None:
            return False
        frame = integer(snapshot["frame"])
        cycle = integer(snapshot["nativeCycle"])
        require(snapshot.get("fieldAvailable") is True
                and snapshot.get("observationBoundary") == "main-task-queue-completion", "unknown field boundary")
        require(isinstance(step,dict) and len(step["keys"]) == 1 and step["keys"][0] in DIRECTIONS,
                "no single requested cardinal step")
        dx,dz,direction,held = DIRECTIONS[step["keys"][0]]
        origin,target = step["origin"],step["target"]
        require(isinstance(origin,list) and len(origin) == 2
                and all(type(v) is int and 0 <= v <= 32767 for v in origin)
                and target == [origin[0]+dx,origin[1]+dz]
                and step["start"] == [v*65536+32768 for v in origin], "requested geometry differs")
        current_context = context(snapshot["context"])
        require(context(step["inputContext"]) == current_context and step["startMap"] == current_context["mapId"],
                "requested field context changed")
        player = snapshot["player"]
        flags = integer(player["flags"])
        require(flags & 1 and not flags & 2 and integer(player["facing"],0,3) == direction
                and integer(snapshot["selector"]["heldKeys"]) & 0xF0 == held
                and player["pos_y"] == step["initialHeight"], "player/input owner changed")
        require(not any(a.get("active") is True and a.get("role") == "MOUNTED" for a in snapshot["actors"]),
                "mounted role is not an unmounted wait")
        requested = dict(origin=origin, target=target, start=step["start"], direction=direction,
                         context=current_context, startFrame=step["startFrame"], height=step["initialHeight"])
        if self.active is not None:
            require(requested == self.active["request"] and frame == self.active["lastFrame"]+1
                    and cycle >= self.active["lastNativeCycle"], "wait request or dense boundary changed")
        receipt = receipts[0] if receipts else None
        mask = None
        if receipt is not None:
            pointer = integer(receipt["objectPointer"], 0x02000000, 0x023FFED4)
            require(not pointer & 3 and integer(receipt["frame"]) == frame
                    and integer(receipt["direction"],0,3) == direction and receipt["origin"] == origin
                    and receipt["target"] == target and context(receipt["context"]) == current_context,
                    "collision receipt is stale or belongs to another request")
            if "nativeCycle" in receipt:
                integer(receipt["nativeCycle"], 1, cycle)
            if "returnNativeCycle" in receipt:
                integer(receipt["returnNativeCycle"], 1, cycle)
                require("nativeCycle" not in receipt or receipt["nativeCycle"] == receipt["returnNativeCycle"],
                        "native return cycle differs")
            for key in ("nativeCycle", "returnNativeCycle"):
                if key in receipt and self.active is not None:
                    require(receipt[key] >= self.active["lastNativeCycle"], "collision receipt precedes prior sample")
            require(self.active is None or pointer == self.active["objectPointer"], "collision object changed")
            for key in ("objectBefore", "objectAfter"):
                if key in receipt:
                    value = receipt[key]
                    require(tile(value) == origin and pose(value) == step["start"]
                            and value["pos_y"] == step["initialHeight"], "collision read changed native pose")
            mask = integer(receipt["collisionMask"])
            require(mask in (0,2), "collision is not the exact object-only mask")
        require(not admitted or mask == 0, "admission lacks exact clear receipt")
        if mask == 0:
            if admitted:
                require(tile(player) == target and [player["x_prev"],player["y_prev"]] == origin
                        and all(min(a,b) <= p <= max(a,b) for a,b,p in
                            zip(step["start"],step["targetRender"],pose(player))), "clear admission pose differs")
            else:
                require(tile(player) == origin and pose(player) == step["start"], "clear moved without admission")
            if self.active is not None:
                require(frame-self.active["startFrame"] <= MAX_WAIT_FRAMES, "collision wait exceeded 120 frames")
                self.active.update(endFrame=frame, clear=deepcopy(receipt), waitingFrames=frame-self.active["startFrame"])
                self.active = None
            return False
        require(not step.get("accepted") and not admitted and tile(player) == origin
                and pose(player) == step["start"]
                and [player["x_prev"],player["y_prev"]] == origin, "blocked player is not stationary and unadmitted")
        if self.active is None:
            require(mask == 2 and len(self.proofs) < 65535, "unbounded or unproved collision wait")
            self.active = dict(startFrame=frame, endFrame=None, request=deepcopy(requested),
                objectPointer=pointer, lastBlockedFrame=frame, lastFrame=frame,
                lastNativeCycle=cycle, waitingFrames=0, blocked=[], clear=None,
                scope="native object-only collision wait; zero active-movement credit")
            self.proofs.append(self.active)
        require(frame-self.active["startFrame"] < MAX_WAIT_FRAMES, "collision wait exceeded 120 frames")
        if mask == 2:
            self.active["lastBlockedFrame"] = frame
            self.active["blocked"].append(deepcopy(receipt))
        require(frame-self.active["lastBlockedFrame"] <= MAX_RECEIPT_GAP, "blocked receipt older than eighteen frames")
        self.active.update(lastFrame=frame, lastNativeCycle=cycle,
                           waitingFrames=frame-self.active["startFrame"]+1)
        return True
