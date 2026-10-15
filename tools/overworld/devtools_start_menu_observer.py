"""Read the stock START menu cursor from a paused private game session."""

import struct


START_MENU_CALLBACK = 0x0203BEF1
SAVE_ACTION = 4
SAVE_APP_CALLBACK = 0x0225D701


def observe_save_app(read, field):
    """Read the stock app controller and Save task while START waits for it."""
    controller = struct.unpack("<I", read(field + 0xD8, 4))[0]
    if not 0x02000000 <= controller <= 0x02400000 - 28 or controller % 4:
        raise ValueError("field app controller pointer is invalid")
    controller_data = struct.unpack_from("<I", read(controller, 28), 16)[0]
    if not 0x02000000 <= controller_data <= 0x02400000 - 16 or controller_data % 4:
        raise ValueError("field app controller data is invalid")
    data = read(controller_data, 16)
    app_id, phase, requested = data[:3]
    app_task = struct.unpack_from("<I", data, 4)[0]
    result = {"appId": app_id, "phase": phase, "requestedAppId": requested,
              "task": app_task}
    if app_task:
        if not 0x02000000 <= app_task <= 0x02400000 - 28 or app_task % 4:
            raise ValueError("field app task pointer is invalid")
        task_data = read(app_task, 28)
        payload, callback = struct.unpack_from("<II", task_data, 16)
        result["callback"] = callback
        if callback == SAVE_APP_CALLBACK:
            if not 0x02000000 <= payload <= 0x02400000 - 0x20 or payload % 4:
                raise ValueError("Save app payload pointer is invalid")
            save = read(payload, 0x20)
            owner = struct.unpack_from("<I", save, 0x1C)[0]
            if owner != field:
                raise ValueError("Save app field owner differs")
            result["save"] = {"state": struct.unpack_from("<I", save, 0x0C)[0],
                              "stateAfterText": struct.unpack_from("<I", save, 0x10)[0],
                              "waitFrames": struct.unpack_from("<I", save, 0x14)[0]}
    return result


def observe_start_menu(read, field, function, owner, env):
    """Decode only the authenticated START-menu task and its bounded payload."""
    if function != START_MENU_CALLBACK or owner != field:
        raise ValueError("START-menu task callback or owner differs")
    if (env % 4 or field % 4 or not 0x02000000 <= env <= 0x02400000 - 0x44
            or not 0x02000000 <= field <= 0x02400000 - 0xD4):
        raise ValueError("START-menu environment or field pointer is invalid")

    data = read(env, 0x44)
    cursor_active, initial_index, state = struct.unpack_from("<IHH", data, 0x20)
    count = struct.unpack_from("<I", data, 0x2C)[0]
    if cursor_active not in (0, 1) or state > 20 or count > 10:
        raise ValueError("START-menu state or action count is invalid")
    if cursor_active and count == 0:
        raise ValueError("active START-menu cursor has no actions")
    actions = list(data[0x3A:0x3A + count])
    if any(action > 12 for action in actions) or actions.count(SAVE_ACTION) > 1:
        raise ValueError("START-menu action mapping is invalid")
    current_index = read(field + 0xD3, 1)[0]
    ready = state == 3 and cursor_active == 1
    if ready and current_index >= count:
        raise ValueError("START-menu current index is outside its action list")
    save_index = actions.index(SAVE_ACTION) if SAVE_ACTION in actions else None
    result = {"ready": ready, "state": state, "cursorActive": bool(cursor_active),
            "initialIndex": initial_index, "currentIndex": current_index if ready else None,
            "currentAction": actions[current_index] if ready else None,
            "saveIndex": save_index, "actions": actions,
            "scope": "paused START-menu task; action 4 is Save"}
    if state == 7:
        result["saveApp"] = observe_save_app(read, field)
    return result
