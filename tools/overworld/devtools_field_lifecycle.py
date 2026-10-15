"""Read-only stock field lifecycle context, never transition acceptance.

Sources: field_system.h/c, overlay_manager.h/c, overlay_01_021E5900.s
and ov01_021F50F0/ov01_021F62CC in overlay_01_021F4704.s. authenticate(address, size)
must verify the current loaded code against the current package; it returns
None/True on success or raises/returns False on failure. No cached pointers.
"""
import struct

MAX_READ_BYTES = 512
# Current Field1 retains stock Init/Exec and admits Exit through the exact
# appearance drain wrapper. The unchanged stock Exit remains its callee.
FIELD_TEMPLATE = (0x021E5925, 0x021E5BE5, 0x02208701, 0xFFFFFFFF)
FIELD_EXIT_WRAPPER = (0x02208700, 56)


def observe_field_lifecycle(read, authenticate, field, frame, native_cycle):
    result = {"frame": frame, "nativeCycle": native_cycle, "fieldPointer": field,
              "boundary": "paused-native-cycle-end", "diagnosticOnly": True,
              "acceptedProof": False, "known": False, "state": "unknown",
              "reason": "unread", "fieldReady": None, "control": None,
              "manager": None, "terrain": None, "readBytes": 0}

    def require(ok, reason):
        if not ok:
            raise ValueError(reason)

    def pointer(value, size):
        require(type(value) is int and value % 4 == 0
                and 0x02000000 <= value <= 0x02400000 - size, "invalid-pointer")
        return value

    def raw(address, size):
        require(type(address) is int and 0x02000000 <= address <= 0x02400000 - size,
                "invalid-read-range")
        require(result["readBytes"] + size <= MAX_READ_BYTES, "read-budget-exceeded")
        result["readBytes"] += size
        data = read(address, size)
        require(isinstance(data, (bytes, bytearray)) and len(data) == size, "short-read")
        return data

    def word(address):
        return struct.unpack("<I", raw(address, 4))[0]

    def code(address, size):
        require(authenticate(address, size) is not False, "code-identity-mismatch")

    def done(state, reason):
        result.update(known=True, state=state, reason=reason)
        return result

    try:
        require(type(frame) is int and frame >= 0 and type(native_cycle) is int
                and native_cycle >= 0, "invalid-clock")
        pointer(field, 0x70)
        # Read this first: a later invalid manager must not hide the leave flag.
        ready = result["fieldReady"] = word(field + 0x6C)
        require(ready in (0, 1), "invalid-field-ready")
        control = pointer(word(field), 16)
        manager, application, paused, exiting = struct.unpack("<4I", raw(control, 16))
        result["control"] = {"pointer": control, "fieldOverlayManager": manager,
                             "applicationManager": application, "isPaused": paused,
                             "exitRequested": exiting}
        require(paused in (0, 1) and exiting in (0, 1), "invalid-control-flags")
        if application:
            pointer(application, 40)
        if not manager:
            return done("field-manager-absent", "application-present" if application else "no-manager")
        pointer(manager, 40)
        values = struct.unpack("<10I", raw(manager, 40))
        init, execute, exit_callback, overlay, exec_state, proc_state, args = values[:7]
        result["manager"] = {"pointer": manager, "init": init, "exec": execute,
                             "exit": exit_callback, "overlayId": overlay,
                             "execState": exec_state, "procState": proc_state,
                             "args": args, "data": values[7]}
        require(values[:4] == FIELD_TEMPLATE, "field-template-mismatch")
        require(args == field, "field-manager-owner-mismatch")
        require(exec_state in (0, 1, 2, 3), "invalid-manager-state")
        code(0x021E5924, 0x2C0)
        code(0x021E5BE4, 0x40)
        code(*FIELD_EXIT_WRAPPER)
        code(0x021E5C24, 0x294)
        if exec_state in (0, 1):
            require(proc_state <= 3, "invalid-field-init-state")
            return done("field-initializing", "field-init-in-progress")
        if exec_state == 2:
            require(proc_state == 0, "invalid-field-exec-state")
        else:
            require(proc_state <= 2, "invalid-field-exit-state")
        if exec_state == 3 and proc_state == 2:
            # Exit phase 1 frees terrain. Do not follow its stale field pointer.
            return done("field-exit-finalizing", "stock-finalizer-pending")
        terrain = pointer(word(field + 0x2C), 0xB4)
        code(0x021F62CC, 0x1C)
        terrain_ready, busy = word(terrain + 0xB0), raw(terrain + 0xA0, 1)[0]
        result["terrain"] = {"pointer": terrain, "readyWord": terrain_ready,
                             "busyByte": busy,
                             "exitPredicate": terrain_ready == 1 and busy == 0}
        # Stock streaming watches a live position against its saved vector.
        # This is diagnostic data only; it cannot grant a stream receipt.
        code(0x021F50F0, 0x3BC)
        pointer(terrain, 0xF4)
        watch = raw(terrain + 0xD0, 36)
        watcher, high, low, active, enabled = struct.unpack_from("<4I", watch, 12) + (
            struct.unpack_from("<I", watch, 32)[0],)
        terrain_result = result["terrain"]
        terrain_result.update(
            sampledPosition=dict(zip(("x", "y", "z"), struct.unpack_from("<3i", watch))),
            watcherPointer=watcher, watcherPosition=None,
            axisHighPointer=high, axisLowPointer=low,
            axisHighValue=None, axisLowValue=None, axisDelta=None,
            axisActive=active, axisDirection=watch[28], watcherEnabled=enabled,
            watchStateHex=watch.hex())
        if watcher:
            terrain_result["watcherPosition"] = dict(zip(("x", "y", "z"),
                struct.unpack("<3i", raw(pointer(watcher, 12), 12))))
        for name, address in (("axisHighValue", high), ("axisLowValue", low)):
            if address:
                terrain_result[name] = struct.unpack("<i", raw(pointer(address, 4), 4))[0]
        if high and low:
            terrain_result["axisDelta"] = (
                terrain_result["axisHighValue"] - terrain_result["axisLowValue"])
        if exec_state == 2:
            return done("field-ready-retained" if ready else "field-exit-pending",
                        "exec-continues-while-ready" if ready else "next-exec-enters-exit")
        if proc_state == 0:
            return done("field-exit-starting", "stock-exit-phase-zero")
        return done("field-exit-terrain-ready" if terrain_ready == 1 and busy == 0
                    else "field-exit-terrain-wait", "stock-terrain-exit-predicate")
    except Exception as error:
        result["reason"] = str(error) if isinstance(error, ValueError) else "reader-or-authentication-failed"
        return result
