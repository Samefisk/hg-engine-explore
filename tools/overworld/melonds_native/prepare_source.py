"""Apply only authenticated interpreter taps to a disposable pinned checkout."""
from pathlib import Path
import hashlib
import subprocess

REVISION = "b86390e4428bf38ce4c1ce0e9ca446d6d25955e8"


def prepare(source):
    source = Path(source)
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if revision != REVISION:
        raise ValueError("melonDS source revision mismatch")
    changed = subprocess.check_output(["git", "-C", str(source), "diff", "--name-only", "HEAD"], text=True).splitlines()
    phase_files = ("NDS.cpp", "GPU3D_Soft.cpp", "GPU2D_Soft.cpp")
    if set(changed) - {"src/" + n for n in ("ARM.cpp", "CP15.cpp") + phase_files}:
        raise ValueError("unexpected changes in pinned melonDS source")
    untracked = subprocess.check_output(["git", "-C", str(source), "ls-files", "--others", "--exclude-standard"], text=True).splitlines()
    if untracked:
        raise ValueError("unexpected untracked files in pinned melonDS source")
    for name in ("ARM.cpp", "CP15.cpp"):
        path = source / "src" / name
        original = subprocess.check_output(["git", "-C", str(source), "show", f"{REVISION}:src/{name}"], text=True)
        patched = original
        include = '#include "ARM.h"'
        if patched.count(include) != 1:
            raise ValueError("ARM include anchor mismatch")
        patched = patched.replace(include, include + '\nbool MD_BeforeInstruction(melonDS::ARM*);\nvoid MD_AfterWrite(melonDS::ARM*, melonDS::u32, melonDS::u32);')
        if name == "ARM.cpp":
            marker = '            if (CPSR & 0x20) // THUMB\n'
            if patched.count(marker) != 2:
                raise ValueError("interpreter dispatch anchor mismatch")
            patched = patched.replace(marker, '            if (MD_BeforeInstruction(this)) continue;\n' + marker)
        owner = "ARMv4" if name == "ARM.cpp" else "ARMv5"
        for suffix, width in (("8", 1), ("16", 2), ("32", 4), ("32S", 4)):
            start = patched.index(f"void {owner}::DataWrite{suffix}(")
            end = patched.index("\n}\n", start) + 3
            body = patched[start:end]
            # The tap follows each successful store. Protection-abort returns
            # are deliberately not tapped. TCM paths bypass the external bus.
            lines = body.splitlines(keepends=True)
            out = []
            stores = 0
            for line in lines:
                out.append(line)
                if (" = val;" in line and ("&ITCM[" in line or "&DTCM[" in line)) or ("    BusWrite" in line and "(addr, val);" in line):
                    out.append(f"    MD_AfterWrite(this, addr, {width});\n")
                    stores += 1
            if stores != (1 if owner == "ARMv4" else 3):
                raise ValueError("CPU store anchor mismatch")
            patched = patched[:start] + "".join(out) + patched[end:]
        # Idempotent only for this exact generated patch; never erase other edits.
        current = path.read_text()
        if current not in (original, patched):
            raise ValueError(f"unrelated source edits: {name}")
        if current != patched:
            path.write_text(patched)
    for name in phase_files:
        path = source / "src" / name
        original = subprocess.check_output(["git", "-C", str(source), "show", f"{REVISION}:src/{name}"], text=True)
        include = '#include "' + name.removesuffix(".cpp") + '.h"'
        if original.count(include) != 1:
            raise ValueError("phase include anchor mismatch: " + name)
        patched = original.replace(include, include + '\n#include "phase_scope.h"')
        if name == "GPU2D_Soft.cpp":
            # GPU.h exposes NDS by reference but does not define its fields.
            patched = patched.replace(include, include + '\n#include "NDS.h"')
        if name == "NDS.cpp":
            for cpu, phase in (("ARM9", 0), ("ARM7", 1)):
                call = cpu + '.Execute<cpuMode>();'
                if patched.count(call) != 1:
                    raise ValueError("phase execute anchor mismatch: " + cpu)
                patched = patched.replace(call, '{ MD_PhaseScope timing(UserData, ' + str(phase) + '); ' + call + ' }')
        else:
            if name == "GPU3D_Soft.cpp":
                anchor = "void SoftRenderer::RenderFrame(GPU& gpu)\n{"
                scope = "MD_PhaseScope timing(gpu.NDS.UserData, 2);"
            else:
                anchor = "void SoftRenderer::DrawScanline(u32 line, Unit* unit)\n{"
                scope = "MD_PhaseScope timing(GPU.NDS.UserData, 3);"
            if patched.count(anchor) != 1:
                raise ValueError("phase renderer anchor mismatch: " + name)
            patched = patched.replace(anchor, anchor + "\n    " + scope)
        previous = patched  # Exact version-1 generated phase instrumentation.
        if name == "NDS.cpp":
            # Restore the pinned original; no Execute-slice clocks in v2.
            patched = original
        elif name == "GPU3D_Soft.cpp":
            patched = previous.replace("MD_PhaseScope timing(gpu.NDS.UserData, 2);",
                                       "MD_PhaseScope timing(gpu.NDS.UserData, 1);")
        else:
            patched = previous.replace("MD_PhaseScope timing(GPU.NDS.UserData, 3);",
                                       "MD_PhaseScope timing(GPU.NDS.UserData, 2);")
        # Only the pinned original, exact prior patch, or exact new patch is
        # accepted. This migration cannot erase unrelated dependency edits.
        current = path.read_text()
        if current not in (original, previous, patched):
            raise ValueError("unrelated source edits: " + name)
        if current != patched:
            path.write_text(patched)
    return REVISION


if __name__ == "__main__":
    import sys
    print(prepare(sys.argv[1]))
