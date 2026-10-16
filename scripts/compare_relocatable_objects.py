"""List functions whose instruction stream or relocations differ between two relocatable objects.

Usage: python3 scripts/compare_relocatable_objects.py OLD.o NEW.o
Build both objects with the production compiler flags (see docs/build diagnosis).
Link addresses are stripped, so only edited functions are reported."""
import collections, re, subprocess, sys
def funcs(path):
    out = subprocess.run(['arm-none-eabi-objdump', '-d', '-r', '--no-show-raw-insn', path], capture_output=True, text=True).stdout
    cur = None; d = collections.OrderedDict()
    for line in out.splitlines():
        m = re.match(r'^[0-9a-f]+ <(.+)>:$', line)
        if m: cur = m.group(1); d[cur] = []; continue
        if cur is None: continue
        line = re.sub(r'^\s+[0-9a-f]+:', '  X:', line)
        line = re.sub(r'[0-9a-f]+ <[^>]*>', '', line)
        line = re.sub(r'\s+@ \(.*?\)$', '', line)
        d[cur].append(line)
    return d
a, b = funcs(sys.argv[1]), funcs(sys.argv[2])
print('functions', len(a), len(b))
print('changed:', sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k)))
