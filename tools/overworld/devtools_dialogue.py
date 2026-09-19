"""Bounded native dialogue state, read only at a completed main task queue.

Layouts: vanilla task.h, script.h, font_types_def.h, sys_task.h, text.c,
render_text.c and overlay_01_021F6830.s / overlay_27.s. No text is copied.
authenticate(address, size) must compare the complete span to current package
code, raising on mismatch (or returning False). Overlay IDs are independently
required before interpreting their code or data. Unknown is never permission.
"""
import hashlib
import json
import struct


TASK_RUN_SCRIPTS = 0x0203FF44
MESSAGE_WAIT = 0x021EF348
BUTTON_WAIT = 0x02041074
MENU_WAIT = 0x020477C0
STANDARD_WAIT = 0x02040BCC
POKECENTER_ANIM = 0x0224BB90
NURSE_FOLLOWER_RECALL = 0x02205B14
BUSY_WAITS = {0x02041CA8: (0x1C, "script-movement"),
              0x02043458: (0x14, "script-fade"),
              0x020408D8: (0x28, "script-timer")}
RUN_TEXT_PRINTER = 0x020202EC
PRINTER_TASKS = 0x021D1F74
PRINTER_SUSPENDED = 0x021D1F6C
TEXT_FLAGS = 0x02111886
MENU_PARENT = 0x021F69C0
MENU_CHILD = 0x0225C434
MENU_DISPATCH = 0x02206C90
MENU_STATES = 0x0225D4D4
MENU_STATE_FUNCTIONS = (0x0225C944, 0x0225C9F8, 0x0225C9E4, 0x0225C94C,
                        0x0225C988, 0x0225C994, 0x0225C9CC, 0x0225CA14,
                        0x0225CA98, 0x0225CC90, 0x0225CCBC, 0x0225CEAC)
MAX_READ_BYTES = 4096


class _Unknown(ValueError):
    pass


def observe_dialogue(read, authenticate, field_pointer, frame, native_cycle, loaded_overlays):
    """Return JSON-safe state; waitIdentity is stable until the native wait changes.

    read(address, size) returns exactly size bytes. At most eight task parents,
    three script contexts, one printer and one menu are read. No cached pointer
    is reused. Only page-wait, yes-no-ready and script-button-wait permit A.
    """
    result = {"frame": frame, "nativeCycle": native_cycle,
              "boundary": "main-task-queue-completion", "fieldPointer": field_pointer,
              "known": False, "state": "unknown", "reason": "unread",
              "script": None, "menu": None, "printer": None, "tasks": [],
              "waitIdentity": None, "readBytes": 0}
    used = 0

    def require(ok, reason):
        if not ok:
            raise _Unknown(reason)

    def pointer(address, size=4):
        require(type(address) is int and address % 4 == 0
                and 0x02000000 <= address <= 0x02400000 - size, "invalid-pointer")
        return address

    def raw(address, size):
        nonlocal used
        require(type(address) is int and 0x02000000 <= address <= 0x02400000 - size,
                "invalid-read-range")
        require(used + size <= MAX_READ_BYTES, "read-budget-exceeded")
        used += size
        value = read(address, size)
        require(isinstance(value, (bytes, bytearray)) and len(value) == size, "short-read")
        return value

    def word(address):
        return struct.unpack("<I", raw(address, 4))[0]

    def code(address, size, overlay=None):
        require(overlay is None or overlay in loaded_overlays, "required-overlay-missing")
        require(authenticate(address, size) is not False, "code-identity-mismatch")

    def finish(state, reason):
        result.update(known=True, state=state, reason=reason)
        if state in ("page-wait", "yes-no-ready", "script-button-wait"):
            identity = {key: result[key] for key in ("fieldPointer", "script", "menu", "printer")}
            # Drop visual/timing counters. Script PC + printer character cursor
            # distinguish consecutive waits even when an allocation is reused.
            identity["state"] = state
            result["waitIdentity"] = hashlib.sha256(json.dumps(
                identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return result

    def menu(ctx):
        code(MENU_WAIT, 0x38)
        code(MENU_PARENT, 0xDC, 1)
        code(0x021F6ABC, 0x54, 1)
        code(MENU_CHILD, 0x78, 27)
        code(0x0225C94C, 0x80, 27)  # ready, dispatch and result handlers
        code(0x0225CD94, 0x118, 27)
        code(MENU_DISPATCH, 16, 1)
        code(MENU_STATES, 48, 27)
        dispatch = struct.unpack("<4I", raw(MENU_DISPATCH, 16))
        require(dispatch == (0x0225C251, 0x0225C399, 0x0225C419, 0xFFFFFFFF),
                "menu-dispatch-mismatch")
        require(struct.unpack("<12I", raw(MENU_STATES, 48)) ==
                tuple(address | 1 for address in MENU_STATE_FUNCTIONS), "menu-state-table-mismatch")
        parent = pointer(word(field_pointer + 0xD8), 28)
        parent_data = raw(parent, 28)
        require(struct.unpack_from("<I", parent_data, 20)[0] == MENU_PARENT | 1,
                "menu-parent-callback-mismatch")
        parent_env = pointer(struct.unpack_from("<I", parent_data, 16)[0], 16)
        parent_data = raw(parent_env, 16)
        require(parent_data[0] == 3 and parent_data[1] == 1, "menu-parent-not-ready")
        require(struct.unpack_from("<I", parent_data, 8)[0] == field_pointer, "menu-parent-owner-mismatch")
        child = pointer(struct.unpack_from("<I", parent_data, 4)[0], 28)
        require(child != parent, "menu-task-cycle")
        child_data = raw(child, 28)
        require(struct.unpack_from("<I", child_data, 20)[0] == MENU_CHILD | 1,
                "menu-child-callback-mismatch")
        env = pointer(struct.unpack_from("<I", child_data, 16)[0], 0x398)
        require(env != parent_env, "menu-environment-alias")
        data = raw(env, 0x28)
        state, output = struct.unpack_from("<2I", data)
        cursor = word(env + 0x394)
        result["menu"] = {"parentTask": parent, "parentEnvironment": parent_env,
                          "task": child, "environment": env, "state": state,
                          "cursor": cursor, "resultPointer": output}
        require(struct.unpack_from("<I", data, 0x1C)[0] == child
                and struct.unpack_from("<I", data, 0x24)[0] == field_pointer,
                "menu-child-owner-mismatch")
        require(output == ctx + 0x68, "menu-result-owner-mismatch")
        require(0 <= state <= 6, "menu-state-unknown")
        if state in (3, 4, 5, 6):
            require(cursor in (0, 1), "menu-cursor-invalid")
        if state == 4 and cursor == 0:
            return finish("yes-no-ready", "yes-selected")
        return finish("busy", "no-selected" if state == 4 else "menu-transition")

    def printer(env):
        code(MESSAGE_WAIT, 0x14, 1)
        code(RUN_TEXT_PRINTER, 0x6C)
        code(0x02020068, 0x18)
        code(0x02002298, 0x558)
        code(0x02002AEC, 0x24)
        code(0x02002B50, 0x3C)
        printer_id = raw(env + 5, 1)[0]
        # 8 is the stock synchronous/instant printer result; 0xFF is failure.
        if printer_id == 8:
            return finish("busy", "synchronous-message-complete")
        require(printer_id < 8, "printer-id-invalid")
        task = word(PRINTER_TASKS + 4 * printer_id)
        if task == 0:
            return finish("busy", "message-printer-complete")
        pointer(task, 28)
        task_data = raw(task, 28)
        require(struct.unpack_from("<I", task_data, 20)[0] == RUN_TEXT_PRINTER | 1,
                "printer-callback-mismatch")
        address = pointer(struct.unpack_from("<I", task_data, 16)[0], 0x34)
        data = raw(address, 0x34)
        char_pointer, window = struct.unpack_from("<2I", data)
        require(0x02000000 <= char_pointer < 0x02400000 and char_pointer % 2 == 0,
                "printer-character-pointer-invalid")
        active, state = data[0x27:0x29]
        require(window == env + 0x14 and data[0x2C] == printer_id, "printer-owner-mismatch")
        # The normal field message creator (sub_0205B5EC) passes NULL.
        # An arbitrary text callback can own the next input/state change.
        require(struct.unpack_from("<I", data, 0x1C)[0] == 0, "printer-text-callback-unknown")
        require(active == 1, "printer-not-active")
        require(state <= 8, "printer-state-unknown")
        flags = raw(TEXT_FLAGS, 2)
        suspended = raw(PRINTER_SUSPENDED, 1)[0]
        result["printer"] = {"id": printer_id, "task": task, "pointer": address,
                             "window": window, "characterPointer": char_pointer,
                             "state": state, "suspended": suspended,
                             "callbackWaiting": data[0x2D], "autoScroll": bool(flags[0] & 4)}
        if suspended or data[0x2D] or flags[0] & 4:
            return finish("busy", "printer-not-input-ready")
        if state in (2, 3):
            return finish("page-wait", "message-page-input")
        return finish("printing", "message-progress")

    try:
        require(type(frame) is int and frame >= 0 and type(native_cycle) is int and native_cycle >= 0,
                "invalid-clock")
        pointer(field_pointer, 0xDC)
        task = word(field_pointer + 0x10)
        if task == 0:
            return finish("idle", "no-field-task")
        code(TASK_RUN_SCRIPTS, 0xD8)
        seen, owners, children = set(), [], []
        while task:
            require(task not in seen, "task-chain-cycle")
            require(len(seen) < 8, "task-chain-limit")
            seen.add(task)
            pointer(task, 32)
            previous, callback, _, env, _, _, owner, _ = struct.unpack("<8I", raw(task, 32))
            result["tasks"].append({"pointer": task, "callback": callback, "environment": env})
            require(owner == field_pointer, "task-owner-mismatch")
            if callback == TASK_RUN_SCRIPTS | 1:
                owners.append((task, env))
            elif callback in (POKECENTER_ANIM | 1, NURSE_FOLLOWER_RECALL | 1):
                if callback == POKECENTER_ANIM | 1:
                    code(POKECENTER_ANIM, 0x258, 2)
                else:
                    code(NURSE_FOLLOWER_RECALL, 0x1DC, 1)
                children.append((task, previous, env, callback))
            else:
                raise _Unknown("task-callback-unknown")
            task = previous
        require(len(owners) == 1, "script-owner-count")
        task, env = owners[0]
        pointer(env, 0xE0)
        data = raw(env, 0x44)
        require(struct.unpack_from("<I", data)[0] == 222271, "script-environment-magic")
        state, count = data[4], data[9]
        contexts = struct.unpack_from("<3I", data, 0x38)
        result["script"] = {"task": task, "environment": env, "state": state,
                            "activeContextCount": count, "contextPointers": list(contexts),
                            "standardWaitMask": data[7], "contexts": [],
                            "scriptNumber": struct.unpack_from("<H", data, 10)[0]}
        if state == 0 and count == 0 and contexts == (0, 0, 0):
            return finish("busy", "script-starting")
        require(state == 1 and 1 <= count <= 3 and sum(bool(c) for c in contexts) == count,
                "script-context-count-or-state")
        # CallStd appends context[count], assigns its slot as id, sets the
        # parent's env.unk_7 bit and puts that parent in ScrNative_WaitStd.
        # RunScript is concurrent instead: never infer input ownership there.
        require(all(contexts[:count]) and not any(contexts[count:])
                and len(set(contexts[:count])) == count, "script-context-chain-invalid")
        require(data[7] == (1 << (count - 1)) - 1, "script-standard-wait-mask-invalid")
        if count > 1:
            code(0x02040B68, 0x64)  # CallStd, including WaitStd pointer literal
            code(STANDARD_WAIT, 0x30)
            code(0x02040BFC, 0x30)  # RestartCurrentScript clears parent bit
        for index, ctx in enumerate(contexts[:count]):
            pointer(ctx, 0x84)
            data = raw(ctx, 0x84)
            mode = data[1]
            callback, script_pc = struct.unpack_from("<2I", data, 4)
            ctx_task = struct.unpack_from("<I", data, 0x74)[0]
            result["script"]["contexts"].append({"pointer": ctx, "id": data[3],
                "mode": mode, "callback": callback, "scriptPointer": script_pc,
                "task": ctx_task, "fieldPointer": struct.unpack_from("<I", data, 0x80)[0]})
            require(data[3] == index, "script-context-id-invalid")
            require(struct.unpack_from("<I", data, 0x80)[0] == field_pointer and ctx_task == task,
                    "script-context-owner-mismatch")
            require(0x02000000 <= script_pc < 0x02400000 or mode == 0,
                    "script-pointer-invalid")
            if index < count - 1:
                require(mode == 2 and callback == STANDARD_WAIT | 1,
                        "script-parent-not-standard-wait")
        result["script"].update(context=ctx, mode=mode, callback=callback, scriptPointer=script_pc)
        require(mode in (0, 1, 2), "script-mode-unknown")
        if children:
            require(len(children) == 1 and len(result["tasks"]) == 2,
                    "healing-task-chain-mismatch")
            child, previous, child_env, child_callback = children[0]
            require(result["tasks"][0]["pointer"] == child and previous == task
                    and child_env != env, "healing-task-owner-mismatch")
            require(mode == 1, "healing-parent-not-bytecode")
            if child_callback == NURSE_FOLLOWER_RECALL | 1:
                pointer(child_env, 0x48)
                phase, index, delay, sequence = raw(child_env, 4)
                require(phase <= 7 and index <= 8 and delay <= 20 and sequence <= 2,
                        "nurse-recall-state-invalid")
                result["script"]["childTask"] = {"pointer": child, "environment": child_env,
                    "callback": child_callback, "state": phase, "index": index,
                    "delay": delay, "sequence": sequence}
                return finish("busy", "nurse-follower-recall")
            pointer(child_env, 0x18)
            child_data = raw(child_env, 0x18)
            count, index, delay, phase = child_data[12:16]
            require(1 <= count <= 6 and index <= count and delay <= 12 and phase <= 5,
                    "healing-task-state-invalid")
            result["script"]["childTask"] = {"pointer": child, "environment": child_env,
                "callback": POKECENTER_ANIM | 1, "state": phase, "count": count,
                "index": index, "delay": delay}
            return finish("busy", "pokecenter-animation")
        if mode == 0:
            return finish("busy", "script-stopping")
        if mode == 2 and callback == STANDARD_WAIT | 1:
            code(STANDARD_WAIT, 0x30)
            return finish("busy", "standard-script-return")
        require(0x02000000 <= script_pc < 0x02400000, "script-pointer-invalid")
        if mode == 1:
            return finish("busy", "script-bytecode")
        if callback == MESSAGE_WAIT | 1:
            return printer(env)
        if callback == MENU_WAIT | 1:
            return menu(ctx)
        if callback == BUTTON_WAIT | 1:
            code(BUTTON_WAIT, 0x6C)
            return finish("script-button-wait", "script-button-input")
        if callback & 1 and callback & ~1 in BUSY_WAITS:
            size, reason = BUSY_WAITS[callback & ~1]
            code(callback & ~1, size)
            return finish("busy", reason)
        raise _Unknown("script-callback-unknown")
    except Exception as error:
        result.update(known=False, state="unknown", waitIdentity=None,
                      reason=str(error) if isinstance(error, _Unknown) else "reader-or-authentication-failed")
        return result
    finally:
        result["readBytes"] = used
