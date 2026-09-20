#!/usr/bin/env python3

import os
import subprocess
import shutil
import struct
import sys
import hashlib
from datetime import datetime
from pathlib import Path
import _io
import ndspy.codeCompression

if sys.platform.startswith('win'):
    PathVar = os.environ.get('Path')
    Paths = PathVar.split(';')
    PATH = ''
    for candidatePath in Paths:
        if 'devkitARM' in candidatePath:
            PATH = candidatePath
            break
    if PATH == '':
        PATH = 'C://devkitPro//devkitARM//bin'
        if os.path.isdir(PATH) is False:
            print('Devkit not found, trying executables on PATH...')
            PATH = ''

    PREFIX = 'arm-none-eabi-'
    OBJDUMP = os.path.join(PATH, PREFIX + 'objdump')
    NM = os.path.join(PATH, PREFIX + 'nm')
    AS = os.path.join(PATH, PREFIX + 'as')

else:  # Linux, OSX, etc.
    if os.path.exists('/opt/devkitpro/devkitARM/bin/'):
        PREFIX = '/opt/devkitpro/devkitARM/bin/arm-none-eabi-'
    else:
        PREFIX = 'arm-none-eabi-'
    OBJDUMP = (PREFIX + 'objdump')
    if sys.platform.startswith('darwin'):
        NM = ('nm')
    else:
        NM = (PREFIX + 'nm')
    AS = (PREFIX + 'as')


BYTE_REPLACEMENT = 'bytereplacement'
HOOKS = 'hooks'
ARM_HOOKS = 'armhooks'
REPOINTS = 'repoints'
ROUTINE_POINTERS = 'routinepointers'

# step 1:  list folders in a directory
SOURCE = "src"
BUILD = "build"
SRC_FILES = os.listdir(SOURCE)
OVERLAYS = []
for file in SRC_FILES:
    if (".c" not in file
            and "individual" not in file
            and ".ld" not in file
            and file != "overworld_follower_release_overlay2"
            and file != "overworld_follower_selector_icons_overlay2"):
        OVERLAYS.append(file)

# construct output filename list
NEW_OVERLAYS = []
for file in OVERLAYS:
    NEW_OVERLAYS.append(BUILD + "/output_" + file + ".bin")

# repeat to grab individual overlays
SRC_FILES = os.listdir(SOURCE + "/individual")
INDIVIDUAL_OVERLAYS = []
for file in SRC_FILES:
    if ".c" in file:
        INDIVIDUAL_OVERLAYS.append(file[:-1 * len(".c")])

# construct output filename list
NEW_INDIVIDUAL_OVERLAYS = []
for file in INDIVIDUAL_OVERLAYS:
    NEW_INDIVIDUAL_OVERLAYS.append(BUILD + "/output_" + file + ".bin")
print

# treat overlay 129 specially
OUTPUT = BUILD + "/output.bin"

LINKED_SECTIONS = [BUILD + "/linked.o"]
for file in OVERLAYS:
    LINKED_SECTIONS.append(BUILD + "/" + file + "_linked.o")
OFFSET_START_IN_129 = 0x600

def ExtractPointer(byteList: [bytes]):
    pointer = 0
    for a in range(len(byteList)):
        pointer += (int(byteList[a])) << (8 * a)

    return pointer


def GetTextSection(section=0) -> int:
    #return 0
    try:
        # Dump sections
        out = subprocess.check_output([OBJDUMP, '-t', LINKED_SECTIONS[section]])
        lines = out.decode().split('\n')

        # Find text section
        text = filter(lambda x: x.strip().endswith('.text'), lines)
        section = (list(text))[0]

        # Get the offset
        offset = int(section.split(' ')[0], 16)
        return offset

    except:
        print("Error: The insertion process could not be completed.\n"
              + "The linker symbol file was not found. Most likely the compilation process was not completed.")
        sys.exit(1)


def GetSymbols() -> {str: int}:
    ret = {}

    for section in LINKED_SECTIONS:
        #subtract = GetTextSection(section)
        out = subprocess.check_output([NM, section])
        lines = out.decode().split('\n')

        for line in lines:
            parts = line.strip().split()

            if len(parts) < 3:
                continue

            if parts[1].lower() not in {'t', 'd'}:
                continue

            offset = int(parts[0], 16)
            ret[parts[2]] = offset# - subtract

    return ret


def GetSectionSize(section_file: str, section_name: str) -> int:
    try:
        out = subprocess.check_output([OBJDUMP, '-h', section_file])
    except Exception:
        return 0

    for line in out.decode().split('\n'):
        parts = line.strip().split()
        if len(parts) >= 3 and parts[1] == section_name:
            return int(parts[2], 16)

    return 0


def VerifyOverworldWildSpawnsOverlay(linked_path: str, output_path: str, packaged_path: str) -> None:
    entry_name = 'gOverworldWildSpawnsOverlayEntry'
    callback_slots = (
        (0, 'OverworldWildSpawns_OverlayOnPlayerStep'),
        (1, 'OverworldWildSpawns_OverlayTryPrimeBattleFromTalk'),
        (2, 'OverworldWildSpawns_OverlayCleanupPendingBattle'),
        (3, 'OverworldWildSpawns_CleanupResidentData'),
        (4, 'OverworldWildSpawns_OverlayOnPlayerFrame'),
        (5, 'OverworldWildSpawns_OverlayOnFieldBusy'),
        (6, 'OverworldWildSpawns_ApplyTransitionWork'),
        (7, 'OverworldWildSpawns_ValidateHopLandingValue'),
        (8, 'OverworldWildSpawns_CopyNativeShadowValue'),
        (9, 'OverworldWildSpawns_BeginMountSelectedFollower'),
    )
    callback_names = [name for _, name in callback_slots]
    symbols = {}
    output = subprocess.check_output([OBJDUMP, '-t', linked_path]).decode()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[-1] in [entry_name, *callback_names]:
            symbols[parts[-1]] = (int(parts[0], 16), int(parts[-2], 16))

    missing = [name for name in [entry_name, *callback_names] if name not in symbols]
    if missing:
        raise RuntimeError(
            'overlay 149 ABI gate is missing linked symbols: ' + ', '.join(missing)
        )
    entry_address, entry_size = symbols[entry_name]
    overlay_base_address = 0x023CCFD8
    expected_entry_size = 40
    if entry_address != 0x023CD000 or entry_size != expected_entry_size:
        raise RuntimeError(
            f'overlay 149 ABI entry changed: address=0x{entry_address:08X} '
            f'size={entry_size}, expected address=0x023CD000 size={expected_entry_size}'
        )

    with open(output_path, 'rb') as file:
        overlay = file.read()
    with open(packaged_path, 'rb') as file:
        packaged = file.read()
    if overlay != packaged:
        raise RuntimeError('packaged overlay 149 differs from its linked binary')
    entry_offset = entry_address - overlay_base_address
    if entry_offset < 0 or len(overlay) < entry_offset + expected_entry_size:
        raise RuntimeError('overlay 149 is shorter than its exported ABI entry')

    actual_callbacks = struct.unpack_from(
        '<10I',
        overlay,
        entry_offset,
    )
    expected_callbacks_list = [0] * 10
    for slot, name in callback_slots:
        expected_callbacks_list[slot] = symbols[name][0] | 1
    expected_callbacks = tuple(expected_callbacks_list)
    if actual_callbacks != expected_callbacks:
        raise RuntimeError(
            'overlay 149 exported ABI entry does not exactly match its linked callbacks'
        )
    if actual_callbacks[8] != 0x023CD029:
        raise RuntimeError('overlay 149 native-shadow value callback moved')
    digest = hashlib.sha256(overlay).hexdigest()
    print(
        f'overlay 149 ABI gate: entry=0x{entry_address:08X} '
        f'size={entry_size} sha256={digest}'
    )


def VerifyOverworldFieldServiceOverlay(linked_path: str, output_path: str, packaged_path: str) -> None:
    entry_name = 'gOverworldFieldServiceEntry'
    mount_entry_name = 'gOverworldFieldMountPresentationEntry'
    selector_hook_name = 'OverworldFollowerSelector_TaskPoll'
    selector_state_name = 'gOverworldFollowerSelectorStateStorage'
    callback_names = [
        'OverworldFieldService_OnMapHeaderChangedImpl',
        'OverworldFieldService_PollFrameImpl',
        'OverworldFieldService_TryGetEncounterDataIdForMapImpl',
    ]
    mount_callback_names = [
        'OverworldFieldService_SyncMountedPresentation',
        'OverworldFieldService_TerrainStream',
    ]
    symbols = {}
    output = subprocess.check_output([OBJDUMP, '-t', linked_path]).decode()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[-1] in [
                entry_name,
                mount_entry_name,
                selector_hook_name,
                selector_state_name,
                *callback_names,
                *mount_callback_names]:
            symbols[parts[-1]] = (int(parts[0], 16), int(parts[-2], 16))

    missing = [
        name
        for name in [
                entry_name,
                mount_entry_name,
                selector_hook_name,
                selector_state_name,
                *callback_names,
                *mount_callback_names]
        if name not in symbols
    ]
    if missing:
        raise RuntimeError(
            'overlay 131 field-service ABI gate is missing linked symbols: '
            + ', '.join(missing)
        )
    entry_address, entry_size = symbols[entry_name]
    expected_entry_size = 16
    if entry_address != 0x023C8000 or entry_size != expected_entry_size:
        raise RuntimeError(
            f'overlay 131 field-service ABI entry changed: address=0x{entry_address:08X} '
            f'size={entry_size}, expected address=0x023C8000 size={expected_entry_size}'
        )
    mount_entry_address, mount_entry_size = symbols[mount_entry_name]
    if mount_entry_address != 0x023C8154 or mount_entry_size != 16:
        raise RuntimeError(
            'overlay 131 mount-presentation ABI entry changed: '
            f'address=0x{mount_entry_address:08X} size={mount_entry_size}, '
            'expected address=0x023C8154 size=16'
        )
    selector_hook_address, selector_hook_size = symbols[selector_hook_name]
    if selector_hook_address != 0x023C8010:
        raise RuntimeError(
            'overlay 131 follower-selector task poll moved: '
            f'address=0x{selector_hook_address:08X}, expected address=0x023C8010'
        )
    selector_state_address, selector_state_size = symbols[selector_state_name]
    if (selector_state_address != 0x023C8148
            or selector_state_size != 1
            or selector_hook_address + selector_hook_size
                > selector_state_address):
        raise RuntimeError(
            'overlay 131 follower-selector state ABI changed or overlaps the '
            'task poll: '
            f'poll_end=0x{selector_hook_address + selector_hook_size:08X}, '
            f'state=0x{selector_state_address:08X} size={selector_state_size}'
        )

    with open(output_path, 'rb') as file:
        overlay = file.read()
    with open(packaged_path, 'rb') as file:
        packaged = file.read()
    if overlay != packaged:
        raise RuntimeError('packaged overlay 131 differs from its linked binary')
    if len(overlay) < 0x164:
        raise RuntimeError('overlay 131 is shorter than its fixed ABI entries')

    actual_entry = struct.unpack_from('<4I', overlay)
    expected_entry = (
        0x3146574F,
        *(symbols[name][0] | 1 for name in callback_names),
    )
    if actual_entry != expected_entry:
        raise RuntimeError(
            'overlay 131 field-service ABI entry does not exactly match its magic and linked callbacks'
        )
    actual_mount_entry = struct.unpack_from('<IHHII', overlay, 0x154)
    expected_mount_entry = (
        0x50544D57,
        2,
        16,
        *(symbols[name][0] | 1 for name in mount_callback_names),
    )
    if actual_mount_entry != expected_mount_entry:
        raise RuntimeError(
            'overlay 131 mount-presentation ABI entry does not exactly match '
            'its magic, version, size, and linked callbacks'
        )
    digest = hashlib.sha256(overlay).hexdigest()
    print(
        f'overlay 131 field-service ABI gate: entry=0x{entry_address:08X} '
        f'size={entry_size} terrain=0x{symbols[mount_callback_names[1]][0]:08X} '
        f'sha256={digest}'
    )


def VerifyOverworldFollowerSelectorOverlay(
        linked_path: str,
        output_path: str,
        packaged_path: str) -> None:
    entry_name = 'gOverworldFollowerSelectorOverlayEntry'
    callback_names = [
        'OverworldFollowerSelector_ValidateImpl',
        'OverworldFollowerSelectorUI_Open',
        'OverworldFollowerSelectorUI_SetSelection',
        'OverworldFollowerSelectorUI_Update',
        'OverworldFollowerSelectorUI_Close',
        'OverworldFollowerSelectorUI_IsOpen',
        'OverworldFollowerSelectorInput_Filter',
        'OverworldFollowerSelectorInput_Cancel',
        'OverworldFollowerSelectorInput_IsActive',
        'OverworldFollowerSelector_GetSelectedPokemon',
        'OverworldFollowerSelector_GetReleaseDistance',
        'OverworldFollowerSelector_IsReleaseTileAvailable',
        'OverworldFollowerSelector_BuildDirectedDirections',
    ]
    condition_entry_name = 'gOverworldBehaviorConditionServiceEntry'
    condition_callback_names = [
        'OverworldBehaviorCondition_PrepareActor',
        'OverworldBehaviorCondition_EvaluatePrepared',
        'OverworldBehaviorCondition_ValidateResolveRequest',
    ]
    condition_gate_name = 'OverworldBehaviorConditionService_Get'
    symbols = {}
    output = subprocess.check_output([OBJDUMP, '-t', linked_path]).decode()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 6 and parts[-1] in [
                entry_name,
                *callback_names,
                condition_entry_name,
                *condition_callback_names,
                condition_gate_name,
        ]:
            symbols[parts[-1]] = (int(parts[0], 16), int(parts[-2], 16))

    missing = [
        name
        for name in [
            entry_name,
            *callback_names,
            condition_entry_name,
            *condition_callback_names,
            condition_gate_name,
        ]
        if name not in symbols
    ]
    if missing:
        raise RuntimeError(
            'overlay 152 ABI gate is missing linked symbols: '
            + ', '.join(missing)
        )

    entry_address, entry_size = symbols[entry_name]
    expected_entry_address = 0x023C0400
    expected_entry_size = 60
    callback_end = 0x023C22A0
    overlay_end = 0x023C3000
    if (entry_address != expected_entry_address
            or entry_size != expected_entry_size):
        raise RuntimeError(
            f'overlay 152 ABI entry changed: address=0x{entry_address:08X} '
            f'size={entry_size}, expected address=0x{expected_entry_address:08X} '
            f'size={expected_entry_size}'
        )

    for name in callback_names:
        callback_address, _ = symbols[name]
        if not expected_entry_address <= callback_address < callback_end:
            raise RuntimeError(
                f'overlay 152 callback {name} is outside its owned range: '
                f'0x{callback_address:08X}'
            )

    condition_entry_address, condition_entry_size = symbols[condition_entry_name]
    if (condition_entry_address != callback_end or condition_entry_size != 24):
        raise RuntimeError(
            'overlay 152 condition service entry changed: '
            f'address=0x{condition_entry_address:08X} '
            f'size={condition_entry_size}'
        )
    for name in condition_callback_names:
        callback_address, _ = symbols[name]
        if not expected_entry_address < callback_address < overlay_end:
            raise RuntimeError(
                f'overlay 152 condition callback {name} is outside its owned range: '
                f'0x{callback_address:08X}'
            )
    gate_address, _ = symbols[condition_gate_name]
    if gate_address != 0x023C22B8:
        raise RuntimeError(
            'overlay 152 condition service gate moved: '
            f'address=0x{gate_address:08X}'
        )

    with open(output_path, 'rb') as file:
        overlay = file.read()
    with open(packaged_path, 'rb') as file:
        packaged = file.read()
    if overlay != packaged:
        raise RuntimeError('packaged overlay 152 differs from its linked binary')
    if len(overlay) < expected_entry_size:
        raise RuntimeError('overlay 152 is shorter than its exported ABI entry')
    if len(overlay) > overlay_end - expected_entry_address:
        raise RuntimeError('overlay 152 exceeds its owned range')

    actual_header = struct.unpack_from('<IHH', overlay)
    expected_header = (0x3153464F, 5, expected_entry_size)
    if actual_header != expected_header:
        raise RuntimeError(
            'overlay 152 exported ABI magic/version/size does not match'
        )
    actual_callbacks = struct.unpack_from(
        f'<{len(callback_names)}I',
        overlay,
        8,
    )
    expected_callbacks = tuple(
        symbols[name][0] | 1
        for name in callback_names
    )
    if actual_callbacks != expected_callbacks:
        raise RuntimeError(
            'overlay 152 exported ABI does not exactly match its linked '
            'Thumb callbacks'
        )
    if any((pointer & 1) == 0 for pointer in actual_callbacks):
        raise RuntimeError('overlay 152 exported a non-Thumb callback')
    if any(not expected_entry_address <= (pointer & ~1) < callback_end
            for pointer in actual_callbacks):
        raise RuntimeError('overlay 152 exported a callback outside its range')

    condition_header = struct.unpack_from(
        '<IHH4I',
        overlay,
        condition_entry_address - expected_entry_address,
    )
    expected_condition_callbacks = tuple(
        symbols[name][0] | 1
        for name in condition_callback_names
    )
    if condition_header != (
            0x4342574F,
            8,
            condition_entry_size,
            *expected_condition_callbacks,
            0,
    ):
        raise RuntimeError('overlay 152 condition service ABI does not match')

    digest = hashlib.sha256(overlay).hexdigest()
    print(
        f'overlay 152 ABI gate: entry=0x{entry_address:08X} '
        f'size={entry_size} sha256={digest}'
    )


def VerifyOverworldWildRuntimeOverlay(
        linked_path: str,
        output_path: str,
        packaged_path: str) -> None:
    entry_name = 'gOverworldWildRuntimeOverlayEntry'
    walk_owner_entry_name = 'gOverworldActorWalkPolicyOwnerEntry'
    boundary_bridge_name = 'OverworldWildRuntime_ApplyMotionBoundary'
    callback_slots = (
        (0, 'OverworldWildRuntime_ValidateImpl'),
        (1, 'OverworldWildRuntime_QuerySurface'),
        (2, 'OverworldWildRuntime_GetGroundBaseY'),
        (3, 'OverworldWildRuntime_FillActorView'),
        (5, 'OverworldWildRuntime_RequestMotion'),
        (6, 'OverworldRoleController_Reduce'),
        (8, 'OverworldWildRuntime_BindActor'),
        (9, 'OverworldWildRuntime_PlayStepDirtParticle'),
        (10, 'OverworldWildRuntime_PlayLandingHopParticle'),
    )
    callback_names = [name for _, name in callback_slots]
    walk_owner_callback = 'OverworldActorWalkPolicy_Reduce'
    symbols = {}
    output = subprocess.check_output([OBJDUMP, '-t', linked_path]).decode()
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[-1] in [
                entry_name,
                walk_owner_entry_name,
                boundary_bridge_name,
                *callback_names,
                walk_owner_callback,
        ]:
            symbols[parts[-1]] = (int(parts[0], 16), int(parts[-2], 16))

    missing = [
        name
        for name in [
            entry_name,
            walk_owner_entry_name,
            boundary_bridge_name,
            *callback_names,
            walk_owner_callback,
        ]
        if name not in symbols
    ]
    if missing:
        raise RuntimeError(
            'overlay 156 ABI gate is missing linked symbols: '
            + ', '.join(missing)
        )

    entry_address, entry_size = symbols[entry_name]
    expected_entry_address = 0x023BC800
    expected_entry_size = 52
    walk_owner_address, walk_owner_size = symbols[walk_owner_entry_name]
    boundary_bridge_address, boundary_bridge_size = symbols[
        boundary_bridge_name
    ]
    expected_walk_owner_address = 0x023BC834
    expected_walk_owner_size = 12
    overlay_end = 0x023BD400
    if (entry_address != expected_entry_address
            or entry_size != expected_entry_size):
        raise RuntimeError(
            f'overlay 156 ABI entry changed: address=0x{entry_address:08X} '
            f'size={entry_size}, expected address=0x{expected_entry_address:08X} '
            f'size={expected_entry_size}'
        )
    if (walk_owner_address != expected_walk_owner_address
            or walk_owner_size != expected_walk_owner_size):
        raise RuntimeError(
            'overlay 156 actor Walk owner entry changed: '
            f'address=0x{walk_owner_address:08X} size={walk_owner_size}, '
            f'expected address=0x{expected_walk_owner_address:08X} '
            f'size={expected_walk_owner_size}'
        )
    if boundary_bridge_address != 0x023BD350 \
            or not 0 < boundary_bridge_size <= 0x9C:
        raise RuntimeError(
            'overlay 156 Actor Motion boundary bridge changed: '
            f'address=0x{boundary_bridge_address:08X} '
            f'size={boundary_bridge_size}'
        )

    for name in callback_names:
        callback_address, _ = symbols[name]
        callback_code_address = callback_address & ~1
        is_role_controller = name == 'OverworldRoleController_Reduce'
        is_step_particle = (
            name == 'OverworldWildRuntime_PlayStepDirtParticle'
        )
        callback_in_owner = (
            0x023BE240 <= callback_code_address < 0x023BE3D8
            if is_role_controller
            else callback_code_address == 0x023BA130
            if is_step_particle
            else expected_entry_address <= callback_code_address < overlay_end
        )
        if not callback_in_owner:
            raise RuntimeError(
                f'overlay 156 callback {name} is outside its resident owner: '
                f'0x{callback_address:08X}'
            )

    with open(output_path, 'rb') as file:
        overlay = file.read()
    with open(packaged_path, 'rb') as file:
        packaged = file.read()
    if overlay != packaged:
        raise RuntimeError('packaged overlay 156 differs from its linked binary')
    if len(overlay) < expected_walk_owner_address - expected_entry_address \
            + expected_walk_owner_size:
        raise RuntimeError('overlay 156 is shorter than its exported ABI entries')

    actual_header = struct.unpack_from('<IHH', overlay)
    expected_header = (0x3152574F, 17, expected_entry_size)
    if actual_header != expected_header:
        raise RuntimeError(
            'overlay 156 exported ABI magic/version/size does not match'
        )
    actual_callbacks = struct.unpack_from('<11I', overlay, 8)
    expected_callbacks_list = [0] * 11
    for slot, name in callback_slots:
        expected_callbacks_list[slot] = symbols[name][0] | 1
    expected_callbacks = tuple(expected_callbacks_list)
    if actual_callbacks != expected_callbacks:
        raise RuntimeError(
            'overlay 156 exported ABI does not exactly match its linked '
            'Thumb callbacks'
        )
    if actual_callbacks[4] != 0 or actual_callbacks[7] != 0:
        raise RuntimeError('overlay 156 retired callback slots are not zero')
    for slot, name in callback_slots:
        pointer = actual_callbacks[slot]
        if (pointer & 1) == 0:
            raise RuntimeError(
                f'overlay 156 exported non-Thumb callback {name}'
            )
        callback_code_address = pointer & ~1
        callback_in_owner = (
            0x023BE240 <= callback_code_address < 0x023BE3D8
            if name == 'OverworldRoleController_Reduce'
            else callback_code_address == 0x023BA130
            if name == 'OverworldWildRuntime_PlayStepDirtParticle'
            else expected_entry_address <= callback_code_address < overlay_end
        )
        if not callback_in_owner:
            raise RuntimeError(
                f'overlay 156 exported callback {name} outside its resident owner'
            )
    actual_walk_owner_header = struct.unpack_from('<IHH', overlay, 52)
    expected_walk_owner_header = (0x5057574F, 1, expected_walk_owner_size)
    actual_walk_owner_callback = struct.unpack_from('<I', overlay, 60)[0]
    expected_walk_owner_callback = symbols[walk_owner_callback][0] | 1
    if (actual_walk_owner_header != expected_walk_owner_header
            or actual_walk_owner_callback != expected_walk_owner_callback):
        raise RuntimeError(
            'overlay 156 actor Walk owner ABI does not match its linked callback'
        )
    if (actual_walk_owner_callback & 1) == 0:
        raise RuntimeError('overlay 156 actor Walk owner exported non-Thumb code')
    if not expected_entry_address <= (
            actual_walk_owner_callback & ~1) < overlay_end:
        raise RuntimeError(
            'overlay 156 actor Walk owner callback is outside its resident image'
        )

    digest = hashlib.sha256(overlay).hexdigest()
    print(
        f'overlay 156 ABI gate: entry=0x{entry_address:08X} '
        f'size={entry_size} sha256={digest}'
    )


def Hook(rom: _io.BufferedReader, space: int, hookAt: int, register=0, memAddress=0, reentrant=False):
    # Align 2
    if hookAt & 1:
        hookAt -= 1

    rom.seek(hookAt)

    if (register > 7 and register != 0xFF):
        print("Register used to hook at " + str(space) + " is > 7 (r" + str(register) + " used).  Modulo'd by 8.")
        register &= 7

    if (register != 0xFF):
        if hookAt % 4:
            data = bytes([0x01, 0x48 | register, 0x00 | (register << 3), 0x47, 0x0, 0x0])
        else:
            data = bytes([0x00, 0x48 | register, 0x00 | (register << 3), 0x47])
        space += 1
        data += (space.to_bytes(4, 'little'))
    else: # register == 0xFF is an unspecified register
        if (memAddress & 0x08000000):
            print("Error:  Need to specify a memory address (02XXXXXX) for total function replacement instead of an absolute offset.")
            sys.exit(1)
        immediateBase = memAddress + (0x18 if reentrant else 0xE)
        immediate = int((space - immediateBase) / 2)
        immediateHigher = (immediate >> 11) & 0x3FF
        immediateLower = immediate & 0x7FF
        if reentrant:
            # Save this invocation's LR on its current mode stack, then copy
            # arguments 5-8 into an aligned call frame for the replacement.
            # This keeps total replacements with stack arguments ABI-correct.
            data = bytes([
                0x10, 0xB5,       # push {r4, lr}
                0x84, 0xB0,       # sub sp, #0x10
                0x06, 0x9C, 0x00, 0x94, # arg 5: [sp, #0x18] -> [sp]
                0x07, 0x9C, 0x01, 0x94, # arg 6: [sp, #0x1C] -> [sp, #4]
                0x08, 0x9C, 0x02, 0x94, # arg 7: [sp, #0x20] -> [sp, #8]
                0x09, 0x9C, 0x03, 0x94, # arg 8: [sp, #0x24] -> [sp, #0xC]
                immediateHigher & 0xFF, (0xF0 | ((immediateHigher >> 8) & 0x3) | (0x4 if immediateBase > space else 0)),
                immediateLower & 0xFF, (0xF8 | ((immediateLower >> 8) & 0x7)),
                0x04, 0xB0,       # add sp, #0x10
                0x10, 0xBD])      # pop {r4, pc}
        else:
            # requires 0x1C of space
            # see documentation/testing_hook.s for the assembly here
            data = bytes([0x60, 0xB4, 0x04, 0x4D, 0x76, 0x46, 0x2E, 0x60, 0x60, 0xBC,
                # memAddress > space would result in negative immediate
                # i suppose all higher bits would be set and this wouldn't be necessary, but this is a mind safety deal i fear
                immediateHigher & 0xFF, (0xF0 | ((immediateHigher >> 8) & 0x3) | (0x4 if immediateBase > space else 0)),
                immediateLower & 0xFF, (0xF8 | ((immediateLower >> 8) & 0x7)),
                0x01, 0x49, 0x09, 0x68, 0x8F, 0x46])
            data += ((memAddress + 0x18).to_bytes(4, 'little'))
        #print(f"bl construction: space = {space:08X}, hookAt = {hookAt:06X}, memAddress = {memAddress:08X}, immediate = {immediate:06X}, {immediateHigher:03X} {immediateLower:03X}")
        #for i in range(0, len(data)):
        #    print(f"{data[i]:02X}", end=' ')
        #print("")

    rom.write(bytes(data))


def HookARM(rom: _io.BufferedReader, space: int, hookAt: int, register=0):
    # Align 4
    if hookAt & 3:
        hookAt -= hookAt % 4

    rom.seek(hookAt)

    if (register > 12):
        print("Register used to hook at " + str(space) + " is > 12 (r" + str(register) + " used).  Results may be unstable.")

    data = bytes([0x00, 0x00 | register << 4, 0x9F, 0xE5, 0x10 | register, 0xFF, 0x2F, 0xE1])

    data += (space.to_bytes(4, 'little'))
    rom.write(bytes(data))


def Repoint(rom: _io.BufferedReader, space: int, repointAt: int, slideFactor=0):
    rom.seek(repointAt)

    space += (slideFactor)
    data = (space.to_bytes(4, 'little'))
    rom.write(bytes(data))


def ReplaceBytes(rom: _io.BufferedReader, offset: int, data: str):
    ar = offset
    words = data.split()
    for i in range(0, len(words)):
        rom.seek(ar)
        intByte = int(words[i], 16)
        rom.write(bytes(intByte.to_bytes(1, 'big')))
        ar += 1


def TryProcessFileInclusion(line: str, definesDict: dict) -> bool:
    if line.startswith('#include "'):
        try:
            path = line.split('"')[1].strip()
            with open(path, 'r', encoding="UTF-8") as file:
                for line in file:
                    if line.startswith('#define '):
                        try:
                            lineList = line.strip().split()
                            title = lineList[1]

                            if len(lineList) == 2 or lineList[2].startswith('//') or lineList[2].startswith('/*'):
                                define = True
                            else:
                                define = lineList[2]

                            definesDict[title] = define
                        except IndexError:
                            print('Error reading define on line"' + line.strip() + '" in file "' + path + '".')

        except Exception as e:
            print('Error including file on line "' + line.strip() + '".')
            print(e)

        return True  # Inclusion line; don't read otherwise

    return False


def TryProcessConditionalCompilation(line: str, definesDict: dict, conditionals: [(str, bool)]) -> bool:
    line = line.strip()
    upperLine = line.upper()
    numWordsOnLine = len(line.split())

    if upperLine.startswith('#IFDEF ') and numWordsOnLine > 1:
        condition = line.strip().split()[1]
        conditionals.insert(0, (condition, True))  # Insert at front
        return True
    elif upperLine.startswith('#IFNDEF ') and numWordsOnLine > 1:
        condition = line.strip().split()[1]
        conditionals.insert(0, (condition, False))  # Insert at front
        return True
    elif upperLine == '#ELSE':
        if len(conditionals) >= 1:  # At least one statement was pushed before
            condition = conditionals.pop(0)
            if condition[1] is True:
                conditionals.insert(0, (condition[0], False))  # Invert old statement
            else:
                conditionals.insert(0, (condition[0], True))  # Invert old statement
            return True
    elif upperLine == '#ENDIF':
        conditionals.pop(0)  # Remove first element (last pushed)
        return True
    else:
        for condition in conditionals:
            definedType = condition[1]
            condition = condition[0]

            if definedType is True:  # From #ifdef
                if condition not in definesDict:
                    return True  # If something isn't defined then skip the line
            else:  # From #ifndef
                if condition in definesDict:
                    return True  # If something is defined then skip the line

    return False


def install():
    if os.path.isfile(BYTE_REPLACEMENT):
        with open(BYTE_REPLACEMENT, 'r') as replacelist:
            definesDict = {}
            additionalFlags = [flag.removeprefix('-D') for flag in sys.argv if flag.startswith('-D')]
            for flag in additionalFlags:
                definesDict[flag] = True
            conditionals = []
            for line in replacelist:
                if TryProcessFileInclusion(line, definesDict):
                    continue
                if TryProcessConditionalCompilation(line, definesDict, conditionals):
                    continue
                if line.strip().startswith('#') or line.strip() == '':
                    continue

                #offset = int(line[4:13], 16) - 0x08000000
                openbin = line[:4]
                if openbin == "arm9":
                    rom2 = open("base/arm9.bin", 'rb+')
                    offset = int(line[4:13], 16) - 0x02000000 if int(line[4:13], 16) & 0x02000000 else int(line[4:13], 16) - 0x08000000
                else:
                    rom2 = open("base/overlay/overlay_" + openbin + ".bin", 'rb+')
                    with open("base/overarm9.bin", 'rb+') as y9Table:
                        y9Table.seek((int(openbin)*0x20)+0x4) # read the overlay memory address for offset calculation
                        offset = int(line[4:13], 16) - struct.unpack_from("<I", y9Table.read(4))[0] if int(line[4:13], 16) & 0x02000000 else int(line[4:13], 16) - 0x08000000
                try:
                    ReplaceBytes(rom2, offset, line[13:].strip())
                except ValueError:  # Try loading from the defines dict if unrecognizable character
                    newNumber = definesDict[line[13:].strip()]
                    try:
                        newNumber = int(newNumber)
                    except ValueError:
                        newNumber = int(newNumber, 16)

                    if (newNumber >= 16777216): # 32 bits
                        #newNumber = str(hex(newNumber)).split('0x')[1]
                        newNumber = (str(hex(newNumber & 0xFF)).split('0x')[1] + " " + str(hex(newNumber >> 8 & 0xFF)).split('0x')[1] + " " + str(hex(newNumber >> 16 & 0xFF)).split('0x')[1] + " " + str(hex(newNumber >> 24 & 0xFF)).split('0x')[1])
                    elif (newNumber >= 65536): # 24 bits
                        #newNumber = str(hex(newNumber)).split('0x')[1]
                        newNumber = (str(hex(newNumber & 0xFF)).split('0x')[1] + " " + str(hex(newNumber >> 8 & 0xFF)).split('0x')[1] + " " + str(hex(newNumber >> 16 & 0xFF)).split('0x')[1])
                    elif (newNumber >= 256): # 16 bits
                        #newNumber = str(hex(newNumber)).split('0x')[1]
                        newNumber = (str(hex(newNumber & 0xFF)).split('0x')[1] + " " + str(hex(newNumber >> 8 & 0xFF)).split('0x')[1])
                    else:
                        newNumber = str(hex(newNumber)).split('0x')[1]
                    ReplaceBytes(rom2, offset, newNumber)
                rom2.close()


def hook():
    if os.path.isfile(HOOKS):
        table = GetSymbols()
        with open(HOOKS, 'r') as hookList:
            definesDict = {}
            additionalFlags = [flag.removeprefix('-D') for flag in sys.argv if flag.startswith('-D')]
            for flag in additionalFlags:
                definesDict[flag] = True
            conditionals = []
            for line in hookList:
                if TryProcessFileInclusion(line, definesDict):
                    continue
                if TryProcessConditionalCompilation(line, definesDict, conditionals):
                    continue
                if line.strip().startswith('#') or line.strip() == '':
                    continue

                if (len(line.split()) == 4):
                    files, symbol, address, register = line.split()
                else:
                    files, symbol, address = line.split()
                    register = "255"
                reentrant = register.lower() == "reentrant"
                if reentrant:
                    register = "255"
                #offset = int(address, 16) - 0x08000000
                try:
                    code = table[symbol]
                except KeyError:
                    print('Symbol missing:', symbol)
                    continue
                if files == "arm9":
                    rom2 = open("base/arm9.bin", 'rb+')
                    offset = int(address, 16) - 0x02000000 if int(address, 16) & 0x02000000 else int(address, 16) - 0x08000000
                else:
                    rom2 = open("base/overlay/overlay_" + files + ".bin", 'rb+')
                    with open("base/overarm9.bin", 'rb+') as y9Table:
                        y9Table.seek((int(files)*0x20)+0x4) # read the overlay memory address for offset calculation
                        offset = int(address, 16) - struct.unpack_from("<I", y9Table.read(4))[0] if int(address, 16) & 0x02000000 else int(address, 16) - 0x08000000
                Hook(rom2, code, offset, int(register), int(address, 16), reentrant)
                rom2.close()


    if os.path.isfile(ARM_HOOKS):
        table = GetSymbols()
        with open(ARM_HOOKS, 'r') as hookList:
            definesDict = {}
            conditionals = []
            for line in hookList:
                if TryProcessFileInclusion(line, definesDict):
                    continue
                if TryProcessConditionalCompilation(line, definesDict, conditionals):
                    continue
                if line.strip().startswith('#') or line.strip() == '':
                    continue

                files, symbol, address, register = line.split()
                #offset = int(address, 16) - 0x08000000
                try:
                    code = table[symbol]
                except KeyError:
                    print('Symbol missing:', symbol)
                    continue
                if files == "arm9":
                    rom2 = open("base/arm9.bin", 'rb+')
                    offset = int(address, 16) - 0x02000000 if int(address, 16) & 0x02000000 else int(address, 16) - 0x08000000
                else:
                    rom2 = open("base/overlay/overlay_" + files + ".bin", 'rb+')
                    with open("base/overarm9.bin", 'rb+') as y9Table:
                        y9Table.seek((int(files)*0x20)+0x4) # read the overlay memory address for offset calculation
                        offset = int(address, 16) - struct.unpack_from("<I", y9Table.read(4))[0] if int(address, 16) & 0x02000000 else int(address, 16) - 0x08000000
                HookARM(rom2, code, offset, int(register))
                rom2.close()

def writeall():
    OFFECTSFILES = "base/overlay/overlay_0129.bin"
    with open(OFFECTSFILES, 'wb+') as rom:
        print("Inserting code.")
        table = GetSymbols()
        with open(OUTPUT, 'rb') as binary:
            rom.seek(OFFSET_START_IN_129)
            rom.write(binary.read())
            binary.close()
        with open("base/overarm9.bin", "rb+") as y9Table:
            # update overlay 129 entry
            # determine insertion location
            with open(SOURCE + "/linker.ld") as linkerFile:
                for line in linkerFile:
                    if "ORIGIN" in line:
                        address = int(line.split()[4][len("0x"):], 0x10)
                        break
            rom.seek(0, 2)
            memSize = rom.tell()
            y9Table.seek(129*0x20) # seek address
            y9Table.write(struct.pack('<I', 129)) # id
            y9Table.write(struct.pack('<I', address)) # memaddress
            y9Table.write(struct.pack('<I', memSize)) # memsize
            y9Table.write(struct.pack('<I', 0)) # bsssize
            y9Table.write(struct.pack('<I', 0)) # initstart
            y9Table.write(struct.pack('<I', 0)) # initend
            y9Table.write(struct.pack('<I', 129)) # file id
            y9Table.write(struct.pack('<I', 0)) # uncompressed
        rom.close()

    # all of the conglomerated overlays
    for i in range(0, len(OVERLAYS)):
        with open(SOURCE + "/" + OVERLAYS[i] + "/linker.ld") as file:
            line = file.readline()
            # grab first line of format /* Overlay ### */, convert ### to a number
            newOverlay = int(line.split(" ")[2])
            # determine insertion location
            for line in file:
                if "ORIGIN" in line:
                    address = int(line.split()[4][len("0x"):-1], 0x10)
                    break
        with open(f"base/overlay/overlay_{newOverlay:04}.bin", 'wb+') as rom:
            with open(NEW_OVERLAYS[i], 'rb') as binary:
                rom.seek(0)
                rom.write(binary.read())
                binary.close()
            rom.close()
        with open("base/overarm9.bin", "rb+") as y9Table:
            overlayPath = f"base/overlay/overlay_{newOverlay:04}.bin"
            bssSize = GetSectionSize(LINKED_SECTIONS[i + 1], '.bss')
            if newOverlay == 131:
                from verify_pokemon_move_history_capture import current_field_overlay_metadata
                bssSize = current_field_overlay_metadata()[2]

            y9Table.seek(newOverlay*0x20) # seek address
            y9Table.write(struct.pack('<I', newOverlay)) # id
            y9Table.write(struct.pack('<I', address)) # memaddress
            y9Table.write(struct.pack('<I', os.path.getsize(overlayPath))) # memsize
            y9Table.write(struct.pack('<I', bssSize)) # bsssize
            y9Table.write(struct.pack('<I', 0)) # initstart
            y9Table.write(struct.pack('<I', 0)) # initend
            y9Table.write(struct.pack('<I', newOverlay)) # file id
            y9Table.write(struct.pack('<I', 0)) # uncompressed
        if newOverlay == 149:
            VerifyOverworldWildSpawnsOverlay(
                LINKED_SECTIONS[i + 1],
                NEW_OVERLAYS[i],
                overlayPath,
            )
        if newOverlay == 131:
            VerifyOverworldFieldServiceOverlay(
                LINKED_SECTIONS[i + 1],
                NEW_OVERLAYS[i],
                overlayPath,
            )
        if newOverlay == 152:
            VerifyOverworldFollowerSelectorOverlay(
                LINKED_SECTIONS[i + 1],
                NEW_OVERLAYS[i],
                overlayPath,
            )
        if newOverlay == 156:
            VerifyOverworldWildRuntimeOverlay(
                LINKED_SECTIONS[i + 1],
                NEW_OVERLAYS[i],
                overlayPath,
            )
        if newOverlay == 158:
            subprocess.check_call([
                sys.executable,
                "-B",
                "scripts/generate_overworld_actor_system_debug.py",
                "--linked", LINKED_SECTIONS[i + 1],
                "--binary", NEW_OVERLAYS[i],
                "--packaged", overlayPath,
                "--overlay-table", "base/overarm9.bin",
                "--header", "include/overworld_actor_system.h",
                "--internal-header", "include/overworld_actor_system_internal.h",
                "--resolver-header", "include/overworld_behavior_resolver.h",
                "--motion-header", "include/overworld_motion_model.h",
                "--output", "build/overworld-system.debug.json",
                "--objdump", OBJDUMP,
            ])
        #print(f"{OVERLAYS[i]} written to overlay {newOverlay}...")

    # Both overlays must be written before checking this private code-host seam.
    # Reuse the final-ROM guard so build and release cannot disagree on layout.
    from verify_pokemon_move_history_capture import verify_field_terrain_packaging
    field_package = Path("base/overlay/overlay_0131.bin").read_bytes()
    terrain_host_package = Path("base/overlay/overlay_0153.bin").read_bytes()
    if (field_package != Path("build/output_field.bin").read_bytes()
            or terrain_host_package
            != Path("build/output_pokemon_move_history_overlay.bin").read_bytes()):
        raise RuntimeError("Field terrain packaged code differs from linked output")
    verify_field_terrain_packaging(
        Path("build/field_linked.o"),
        Path("build/pokemon_move_history_overlay_linked.o"),
        Path("build/pokemon_move_history_overlay/overworld_field_terrain_stream.o"),
        field_package,
        terrain_host_package,
        OBJDUMP,
    )
    print("Field terrain package gate: resident code, Field state, Thumb arguments verified")

    # all of the individual overlays
    for i in range(0, len(INDIVIDUAL_OVERLAYS)):
        with open(SOURCE + "/individual/linker/" + INDIVIDUAL_OVERLAYS[i] + ".ld") as file:
            line = file.readline()
            # grab first line of format /* Overlay ### */, convert ### to a number
            newOverlay = int(line.split(" ")[2])
            # determine insertion location
            for line in file:
                if "ORIGIN" in line:
                    address = int(line.split()[4][len("0x"):-1], 0x10)
                    break
        with open(f"base/overlay/overlay_{newOverlay:04}.bin", 'wb+') as rom:
            with open(NEW_INDIVIDUAL_OVERLAYS[i], 'rb') as binary:
                rom.seek(0)
                rom.write(binary.read())
                binary.close()
            rom.close()
        with open("base/overarm9.bin", "rb+") as y9Table:
            overlayPath = f"base/overlay/overlay_{newOverlay:04}.bin"
            bssSize = GetSectionSize(BUILD + "/" + INDIVIDUAL_OVERLAYS[i] + "_linked.o", '.bss')

            y9Table.seek(newOverlay*0x20) # seek address
            y9Table.write(struct.pack('<I', newOverlay)) # id
            y9Table.write(struct.pack('<I', address)) # memaddress
            y9Table.write(struct.pack('<I', os.path.getsize(overlayPath))) # memsize
            y9Table.write(struct.pack('<I', bssSize)) # bsssize
            y9Table.write(struct.pack('<I', 0)) # initstart
            y9Table.write(struct.pack('<I', 0)) # initend
            y9Table.write(struct.pack('<I', newOverlay)) # file id
            y9Table.write(struct.pack('<I', 0)) # uncompressed
        #print(f"{INDIVIDUAL_OVERLAYS[i]} written to overlay {newOverlay}...")

    width = max(map(len, table.keys())) + 1
    if os.path.isfile('offsets.ini'):
        offsetIni = open('offsets.ini', 'r+')
    else:
        offsetIni = open('offsets.ini', 'w')

    offsetIni.truncate()
    for key in sorted(table.keys()):
        fstr = ('{:' + str(width) + '} {:08X}')
        offsetIni.write(fstr.format(key + ':', table[key]) + '\n')
    offsetIni.close()


def repoint():
    if os.path.isfile(ROUTINE_POINTERS):
        table = GetSymbols()
        with open(ROUTINE_POINTERS, 'r') as pointerlist:
            definesDict = {}
            conditionals = []
            for line in pointerlist:
                if TryProcessFileInclusion(line, definesDict):
                    continue
                if TryProcessConditionalCompilation(line, definesDict, conditionals):
                    continue
                if line.strip().startswith('#') or line.strip() == '':
                    continue

                files, symbol, address = line.split()
                #offset = int(address, 16) - 0x08000000
                try:
                    code = table[symbol]
                except KeyError:
                    print('Symbol missing:', symbol)
                    continue
                if files == "arm9":
                    rom2 = open("base/arm9.bin", 'rb+')
                    offset = int(address, 16) - 0x02000000 if int(address, 16) & 0x02000000 else int(address, 16) - 0x08000000
                else:
                    rom2 = open("base/overlay/overlay_" + files + ".bin", 'rb+')
                    with open("base/overarm9.bin", 'rb+') as y9Table:
                        y9Table.seek((int(files)*0x20)+0x4) # read the overlay memory address for offset calculation
                        offset = int(address, 16) - struct.unpack_from("<I", y9Table.read(4))[0] if int(address, 16) & 0x02000000 else int(address, 16) - 0x08000000
                Repoint(rom2, code, offset, 1)
                rom2.close()


def offset():
    if os.path.isfile(REPOINTS):
        table = GetSymbols()
        with open(REPOINTS, 'r') as repointList:
            definesDict = {}
            conditionals = []
            for line in repointList:
                if TryProcessFileInclusion(line, definesDict):
                    continue
                if TryProcessConditionalCompilation(line, definesDict, conditionals):
                    continue
                if line.strip().startswith('#') or line.strip() == '':
                    continue

                files, symbol, address = line.split()
                #offset = int(address, 16) - 0x08000000
                try:
                    addOffset = 0
                    if '+' in symbol:
                        symbol, addOffsetStr = symbol.split('+')
                        addOffset = int(addOffsetStr, 16)
                    code = table[symbol]
                except KeyError:
                    print('Symbol missing:', symbol)
                    continue
                if files == "arm9":
                    rom = open("base/arm9.bin", 'rb+')
                    offset = int(address, 16) - 0x02000000 if int(address, 16) & 0x02000000 else int(address, 16) - 0x08000000
                else:
                    rom = open("base/overlay/overlay_" + files + ".bin", 'rb+')
                    with open("base/overarm9.bin", 'rb+') as y9Table:
                        y9Table.seek((int(files)*0x20)+0x4) # read the overlay memory address for offset calculation
                        offset = int(address, 16) - struct.unpack_from("<I", y9Table.read(4))[0] if int(address, 16) & 0x02000000 else int(address, 16) - 0x08000000
                Repoint(rom, code, offset, addOffset)
                rom.close()


OVERLAYS_TO_DECOMPRESS = [1, 2, 6, 7, 8, 10, 12, 14, 15, 18, 23, 31, 61, 63, 64, 65, 68, 70, 94, 96, 112]


def decompress():
    if os.path.exists("build/arm9.bin"):
        os.remove("build/arm9.bin")
    shutil.copyfile("base/arm9.bin", "build/arm9.bin")
    arm9 = open("build/arm9.bin", "wb+")
    FNULL = open(os.devnull, 'w')
    with open("base/arm9.bin", 'rb') as rom:
        bin = rom.read()
        if len(bin) < 0xBC000:
            print("Decompress arm9.")
            dec = bytearray(ndspy.codeCompression.decompress(bin))
            dec[0xbb4] = 0
            dec[0xbb5] = 0
            dec[0xbb6] = 0
            dec[0xbb7] = 0
            arm9.write(dec)
            shutil.copyfile("build/arm9.bin", "base/arm9.bin")
        rom.close()
        arm9.close()
    with open("base/overarm9.bin", 'rb+') as rom:
        for n in OVERLAYS_TO_DECOMPRESS:
            rom.seek((n*0x20)+0x1C) #write 00 00 00 00 to (num*0x20)+0x1C to make game consider overlay num decompressed (and call decompress below)
            bunh = bytes([0x0, 0x0, 0x0, 0x0])
            rom.write(bytes(bunh))
        rom.close()
    for n in OVERLAYS_TO_DECOMPRESS:
        decompress_file("base/overlay/overlay_" + str(n).zfill(4) + ".bin")



def decompress_file(path):
    try:
        with open(path, 'rb') as f:
            dec = ndspy.codeCompression.decompress(f.read())
        with open(path, 'wb') as f:
            f.write(dec)
    except ValueError: # do nothing, file is already decompressed
        print("")



if __name__ == '__main__':
    decompress()
    writeall()
    install()
    hook()
    repoint()
    offset()
