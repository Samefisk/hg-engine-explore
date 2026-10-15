"""Refresh every address/hash seal that tracks the linked Wild overlay.

Run from the repo root only after scripts/compare_relocatable_objects.py shows
that the audited source change touched nothing but the functions it names: all
other sealed bodies then differ only by link-address literals."""
import hashlib, pprint, re, subprocess, sys
sys.path.insert(0, '.'); sys.path.insert(0, 'scripts')
from pathlib import Path
from verify_pokemon_move_history_capture import elf_bytes_at
from pack_overworld_combat_capsules import section_bytes
import pack_overworld_actor_slam_jump as slam

wild = Path('build/overworld_wild_spawns_overlay_linked.o')
nm = subprocess.run(['arm-none-eabi-nm', '-S', str(wild)], capture_output=True, text=True).stdout
table = {}
for line in nm.splitlines():
    p = line.split()
    if len(p) == 4: table[p[3]] = (int(p[0], 16), int(p[1], 16))
sha = lambda b: hashlib.sha256(b).hexdigest()

def sub(path, old, new):
    p = Path(path); t = p.read_text()
    if old not in t: raise SystemExit('seal text missing in %s: %s' % (path, old[:60]))
    p.write_text(t.replace(old, new))

# 1. Slam / driver / pickup seals
driver_address = table[slam.DRIVER][0] & ~1
if driver_address != slam.DRIVER_ADDRESS:
    for f in ('scripts/pack_overworld_actor_slam_jump.py', 'tools/overworld/devtools_slam_admission_observer.py'):
        text = Path(f).read_text()
        old = '0x%08X' % slam.DRIVER_ADDRESS
        if old in text: Path(f).write_text(text.replace(old, '0x%08X' % driver_address))
    print('slam driver address 0x%08X -> 0x%08X' % (slam.DRIVER_ADDRESS, driver_address))
    slam.DRIVER_ADDRESS = driver_address
driver_size = table[slam.DRIVER][1]
if driver_size != slam.DRIVER_SIZE:
    text = Path('scripts/pack_overworld_actor_slam_jump.py').read_text()
    Path('scripts/pack_overworld_actor_slam_jump.py').write_text(
        text.replace('DRIVER_ADDRESS, DRIVER_SIZE = 0x%08X, %d' % (slam.DRIVER_ADDRESS, slam.DRIVER_SIZE),
                     'DRIVER_ADDRESS, DRIVER_SIZE = 0x%08X, %d' % (slam.DRIVER_ADDRESS, driver_size)))
    print('slam driver size', slam.DRIVER_SIZE, '->', driver_size)
    slam.DRIVER_SIZE = driver_size
body = section_bytes(wild, slam.SECTION, slam.ADDRESS, slam.SIZE)
driver = elf_bytes_at(wild, slam.DRIVER_ADDRESS, slam.DRIVER_SIZE)
for old, new in ((slam.BODY_SHA256, sha(body)), (slam.DRIVER_SHA256, sha(driver))):
    if old != new:
        for f in ('scripts/pack_overworld_actor_slam_jump.py', 'tools/overworld/devtools_slam_admission_observer.py'):
            if old in Path(f).read_text(): sub(f, old, new)
        print('slam seal', old[:8], '->', new[:8])

# 2. Entry native owners (verify script + query observer)
import verify_overworld_query_code_addon as v
owners = {}
for name, (_a, _s, overlay, _sha) in v.WILD_ENTRY_NATIVE_OWNERS.items():
    addr, size = table[name]
    owners[name] = (addr | 1, size, overlay, sha(elf_bytes_at(wild, addr & ~1, size)))
path = Path('scripts/verify_overworld_query_code_addon.py'); text = path.read_text()
s = text.index('WILD_ENTRY_NATIVE_OWNERS = {'); e = text.index('\n\nMOUNT_ABSOLUTE_CALLBACKS')
text = text[:s] + 'WILD_ENTRY_NATIVE_OWNERS = ' + pprint.pformat(owners, width=100) + text[e:]
text = re.sub(r"WILD_ENTRY_NATIVE_TABLE_OWNER = \([^)]*\)", "WILD_ENTRY_NATIVE_TABLE_OWNER = (%d, 72, 'OBJECT')" % table[v.WILD_ENTRY_NATIVE_TABLE][0], text)
path.write_text(text)
vals = {}
for key, name in (('ops', 'sOverworldWildEntryNativeOps'), ('remove', 'OverworldWildSpawns_RemoveEncounter'), ('spawn', 'OverworldWildSpawns_SpawnPreparedEncounter')):
    a, sz = table[name]; vals[key] = (a & ~1, sz, sha(elf_bytes_at(wild, a & ~1, sz)))
p = Path('tools/overworld/devtools_query_observer.py'); t = p.read_text()
i = t.index('ENTRY_NATIVE_OWNERS = {'); j = t.index('# Each offset is measured from the actual ARM types')
t = t[:i] + 'ENTRY_NATIVE_OWNERS = {' + ',\n '.join("'%s': (%d, %d, '%s')" % (k, *v2) for k, v2 in vals.items()) + '}\n' + t[j:]
p.write_text(t)

# 3. Fly landing cost pins
def repin(match):
    file, name = match.group(1), match.group(2)
    linked = Path('build') / file
    out = subprocess.run(['arm-none-eabi-nm', '-S', str(linked)], capture_output=True, text=True).stdout
    for line in out.splitlines():
        q = line.split()
        if len(q) == 4 and q[3] == name:
            a, sz = int(q[0], 16) & ~1, int(q[1], 16)
            return '("%s", "%s", 0x%08X, %d, "%s")' % (file, name, a, sz, sha(elf_bytes_at(linked, a, sz)))
    raise SystemExit('missing ' + name)
for pin_file in ('tools/overworld/devtools_fly_landing_cost.py', 'tools/overworld/devtools_slam_admission_observer.py'):
    p = Path(pin_file); t = p.read_text()
    t2 = re.sub(r'\("([^"]+_linked\.o)", "([^"]+)", 0x[0-9A-Fa-f]+, \d+, "[0-9a-f]{64}"\)', repin, t)
    if t2 != t: print('pins refreshed in', pin_file)
    p.write_text(t2)


# 4. Mount verifier: ApplyTransitionWork owner and its retained-mask call site
p = Path('scripts/verify_overworld_mount.py'); t = p.read_text()
addr, size = table['OverworldWildSpawns_ApplyTransitionWork']
addr &= ~1
body_hash = sha(elf_bytes_at(wild, addr, size))
call = subprocess.run(['arm-none-eabi-objdump', '-d', str(wild)], capture_output=True, text=True).stdout
site = [int(l.split(':')[0], 16) for l in call.splitlines()
        if re.search(r'\bbl\s+1fff930\s+<OverworldWildSpawns_RetainedMaskNamesActiveSpawns>', l)]
if len(site) != 1: raise SystemExit('retained-mask call site not unique')
m = re.search(r'require\(symbol == \((0x[0-9A-F]{8}), (\d+), "\.text", "F"\)', t)
old_addr, old_size = int(m.group(1), 16), int(m.group(2))
old_site = int(re.search(r'decode_thumb_bl\(linked_body, 0x[0-9A-F]{8}, (0x[0-9A-F]{8})\)', t).group(1), 16)
old_hash = re.search(r'== "([0-9a-f]{64})"\n\s+and decode_thumb_bl', t).group(1)
t = t.replace('(0x%08X, %d, ".text", "F")' % (old_addr, old_size), '(0x%08X, %d, ".text", "F")' % (addr, size))
t = t.replace('(0x%08X, %d, "FUNC")' % (old_addr | 1, old_size), '(0x%08X, %d, "FUNC")' % (addr | 1, size))
t = t.replace('len(linked_body) == %d and packaged_body == linked_body' % old_size, 'len(linked_body) == %d and packaged_body == linked_body' % size)
t = t.replace(old_hash, body_hash)
t = t.replace('decode_thumb_bl(linked_body, 0x%08X, 0x%08X)' % (old_addr, old_site), 'decode_thumb_bl(linked_body, 0x%08X, 0x%08X)' % (addr, site[0]))
t = t.replace('%x:' % old_site, '%x:' % site[0]).replace('"%x:", "%x:"' % (site[0], site[0] + 2), '"%x:", "%x:"' % (site[0], site[0] + 2))
p.write_text(t)

# 5. Cargo observation: unchanged body whose callee/literal addresses follow the link
import verify_overworld_field_capsule as capsule
cargo = elf_bytes_at(wild, capsule.CARGO_OBSERVATION, capsule.CARGO_OBSERVATION_SIZE)
if sha(cargo) != capsule.CARGO_OBSERVATION_SHA256:
    sub('scripts/verify_overworld_field_capsule.py', capsule.CARGO_OBSERVATION_SHA256, sha(cargo))
    print('cargo observation seal', capsule.CARGO_OBSERVATION_SHA256[:8], '->', sha(cargo)[:8])
if cargo != capsule.CARGO_OBSERVATION_CODE:
    capsule_path = Path('scripts/verify_overworld_field_capsule.py'); capsule_text = capsule_path.read_text()
    start = capsule_text.index('CARGO_OBSERVATION_CODE = bytes.fromhex(')
    end = capsule_text.index('\n)\n', start) + 3
    hexed = cargo.hex()
    block = 'CARGO_OBSERVATION_CODE = bytes.fromhex(\n' + '\n'.join(
        "    '%s'" % hexed[i:i + 64] for i in range(0, len(hexed), 64)) + '\n)\n'
    capsule_path.write_text(capsule_text[:start] + block + capsule_text[end:])
    print('cargo observation reference code refreshed')
capsule_path = Path('scripts/verify_overworld_field_capsule.py'); capsule_text = capsule_path.read_text()
for symbol in ('OverworldWildSpawns_AbortThrow', 'OverworldWildSpawns_QueryPickupThrowTarget',
               'OverworldWildSpawns_QueryAddon', 'OverworldWildSpawns_IsCurrentSpawnObject'):
    name = {'OverworldWildSpawns_AbortThrow': 'abort', 'OverworldWildSpawns_QueryPickupThrowTarget': 'query_target',
            'OverworldWildSpawns_QueryAddon': 'query', 'OverworldWildSpawns_IsCurrentSpawnObject': 'identity'}[symbol]
    a, sz = table[symbol]
    capsule_text, n = re.subn(r'\(%s, 0x[0-9A-Fa-f]{8}, \d+\)' % name, '(%s, 0x%08X, %d)' % (name, a & ~1, sz), capsule_text)
    if n != 1: raise SystemExit('cargo target pin missing: ' + name)
capsule_text = re.sub(r'(NOTICE_CLEAR_RELATIONS_ADDR, NOTICE_CLEAR_RELATIONS_SIZE = )0x[0-9A-F]{8}, \d+',
    lambda m: '%s0x%08X, %d' % (m.group(1), table['OverworldWildSpawns_ClearThrowRelations'][0] & ~1,
                               table['OverworldWildSpawns_ClearThrowRelations'][1]), capsule_text)
notice = sha(elf_bytes_at(wild, capsule.NOTICE_CALLERS, capsule.NOTICE_PHYSICAL_SIZE))
capsule_text = re.sub(r'NOTICE_PHYSICAL_SHA256 = "[0-9a-f]{64}"', 'NOTICE_PHYSICAL_SHA256 = "%s"' % notice, capsule_text)
tail = sha(elf_bytes_at(wild, capsule.NOTICE_CLEAR_THROW_ADDR, capsule.NOTICE_CLEAR_THROW_SIZE))
capsule_text = re.sub(r'(hashlib\.sha256\(tail\)\.hexdigest\(\)\n\s*== ")[0-9a-f]{64}', lambda m: m.group(1) + tail, capsule_text)
capsule_path.write_text(capsule_text)

# 6. Observer pins for the helper position scanner and its callback table
helper = Path('build/overworld_wild_helper_overlay_linked.o')
def nm_table(path):
    out = {}
    for line in subprocess.run(['arm-none-eabi-nm', '-S', str(path)], capture_output=True, text=True).stdout.splitlines():
        q = line.split()
        if len(q) == 4: out[q[3]] = (int(q[0], 16), int(q[1], 16))
    return out
helper_table = nm_table(helper)
observer_path = Path('tools/overworld/devtools_observer.py'); observer = observer_path.read_text()
scan_name = 'OverworldWildHelper_TryPickSpawnPositionForTerrain.constprop.0'
owners = {}
for key, home, name in (('helper', 'helper', 'OverworldWildHelper_TryPrepareSpawn'), ('scanner', 'helper', scan_name),
                        ('terrain', 'wild', 'OverworldWildSpawns_HelperTryGetSpawnTerrain'),
                        ('occupied', 'wild', 'OverworldWildSpawns_HelperIsTileOccupied'),
                        ('near', 'wild', 'OverworldWildSpawns_HelperIsNearActiveSpawn')):
    address, size = (helper_table if home == 'helper' else table)[name]
    address &= ~1
    owners[key] = (home, name, address, size, sha(elf_bytes_at(helper if home == 'helper' else wild, address, size)))
observer = re.sub(r"HELPER_SCAN_OWNERS = \{.*?\}\n", 'HELPER_SCAN_OWNERS = ' + repr(owners) + '\n', observer, count=1, flags=re.S)
tbl_address, tbl_size = table['sOverworldWildSpawnPrepCallbacks']
observer = re.sub(r"HELPER_SCAN_TABLE_SHA = '[0-9a-f]{64}'", "HELPER_SCAN_TABLE_SHA = '%s'" % sha(elf_bytes_at(wild, tbl_address, tbl_size)), observer)
dis = subprocess.run(['arm-none-eabi-objdump', '-d', '-M', 'force-thumb', str(helper)], capture_output=True, text=True).stdout.splitlines()
scan_lo, scan_size = helper_table[scan_name]
sites = {}
for index, line in enumerate(dis):
    m = re.match(r'\s*([0-9a-f]+):\s+[0-9a-f]+\s+ldr\s+r\d, \[r\d, #(4|8|12)\]', line)
    if m and scan_lo <= int(m.group(1), 16) < scan_lo + scan_size:
        for follow in dis[index + 1:index + 4]:
            b = re.match(r'\s*([0-9a-f]+):\s+[0-9a-f]+\s+blx\s+r\d', follow)
            if b:
                sites[{'4': 'terrain', '8': 'occupied', '12': 'near'}[m.group(2)]] = int(b.group(1), 16)  # last loop site wins
                break
assert set(sites) == {'terrain', 'occupied', 'near'}, sites
observer = re.sub(r"HELPER_SCAN_CALL_SITES = \{[^}]*\}", 'HELPER_SCAN_CALL_SITES = {%s}' % ', '.join("'%s': 0x%08X" % (k, sites[k]) for k in ('terrain', 'occupied', 'near')), observer)
cursor_address = helper_table['sOverworldWildHelperSpawnPositionCursor'][0]
observer = re.sub(r"cursor\[:2\] != \(0x[0-9A-F]{8}, 4\)", 'cursor[:2] != (0x%08X, 4)' % cursor_address, observer)
observer = re.sub(r"table\[:2\] != \(0x[0-9A-F]{8}, 36\)", 'table[:2] != (0x%08X, 36)' % tbl_address, observer)
observer_path.write_text(observer)
print('helper scanner observer pins refreshed')

# 7. Pickup-cancel and Rest-tint bodies carry link-address literals
pickup = section_bytes(wild, slam.PICKUP_SECTION, slam.PICKUP_ADDRESS, slam.PICKUP_SIZE)
if sha(pickup) != slam.PICKUP_SHA256:
    sub('scripts/pack_overworld_actor_slam_jump.py', slam.PICKUP_SHA256, sha(pickup))
    print('pickup cancel seal', slam.PICKUP_SHA256[:8], '->', sha(pickup)[:8])
import pack_overworld_field_capsule as field_capsule
rest = section_bytes(Path('build/overworld_field_capsule_linked.o'), field_capsule.REST_POLICY_SECTION,
                     field_capsule.REST_POLICY_ADDRESS, field_capsule.REST_POLICY_SIZE)
if sha(rest) != field_capsule.REST_POLICY_SHA256:
    sub('scripts/pack_overworld_field_capsule.py', field_capsule.REST_POLICY_SHA256, sha(rest))
    print('rest tint seal', field_capsule.REST_POLICY_SHA256[:8], '->', sha(rest)[:8])

# 8. Query-image resolver body pinned by the field capsule verifier (relative BLs follow earlier Query code)
from verify_pokemon_move_history_capture import packaged_thumb_calls
query_elf = Path('build/overworld_query_code_addon/image.elf')
q_address, q_size = nm_table(query_elf)['BehaviorResolver_ApplyRecorded']
q_address &= ~1
q_body = elf_bytes_at(query_elf, q_address, q_size)
capsule_text = Path('scripts/verify_overworld_field_capsule.py').read_text()
m = re.search(r'caller\[:3\] == \(0x([0-9a-f]+), (\d+), "FUNC"\)', capsule_text)
if int(m.group(1), 16) != q_address | 1 or int(m.group(2)) != q_size:
    raise SystemExit('profile merge owner moved: update its pinned address/size by hand')
capsule_text = re.sub(r'(hashlib\.sha256\(linked\)\.hexdigest\(\)\n\s*== ")[0-9a-f]{64}', lambda k: k.group(1) + sha(q_body), capsule_text)
calls = packaged_thumb_calls(q_body, q_address, q_address, q_size)
rows = ',\n                '.join('(0x%x, "%s", %s)' % (a, k, ('0x%x' % t) if isinstance(t, int) and k == 'bl' else t) for a, k, t in calls)
capsule_text = re.sub(r'packaged_thumb_calls\(linked, 0x[0-9a-f]+, 0x[0-9a-f]+, 380\) == \[.*?\],\n(\s*"profile merge)',
    lambda k: 'packaged_thumb_calls(linked, 0x%x, 0x%x, 380) == [\n                %s],\n%s' % (q_address, q_address, rows, k.group(1)), capsule_text, flags=re.S)
Path('scripts/verify_overworld_field_capsule.py').write_text(capsule_text)
print('query profile-merge pin refreshed')

# 9. Fixed-extent publication owners whose size follows catalog-count immediates
query_verifier = Path('scripts/verify_overworld_query_code_addon.py'); query_text = query_verifier.read_text()
def refresh_owner(match):
    name, overlay, filename, address, size, extent = match.groups()
    symbols = nm_table(Path('build') / filename)
    actual_address, actual_size = symbols[name]
    assert (actual_address | 1) == int(address, 16) or actual_address == int(address, 16), (name, hex(actual_address))
    return '"%s": (%s, "%s", %s, %d, %s)' % (name, overlay, filename, address, actual_size, extent)
query_text = re.sub(r'"(OverworldConditionPublication_\w+)": \((\d+), "([^"]+)", (0x[0-9A-Fa-f]+), (\d+), (\d+)\)', refresh_owner, query_text)
query_verifier.write_text(query_text)
print('publication owner sizes refreshed')

# 10. Query-image native owner bodies: same address/extent, link-count literals changed
import importlib
import verify_overworld_query_code_addon as qv
importlib.reload(qv)
query_text = Path('scripts/verify_overworld_query_code_addon.py').read_text()
query_symbols = nm_table(query_elf)
for owners_name, sha_name in (('CONDITION_NATIVE_OWNERS', 'CONDITION_NATIVE_SHA256'), ('RESOLVER_NATIVE_OWNERS', 'RESOLVER_NATIVE_SHA256'),
                              ('CONDITION_RUNTIME_CALLBACK_OWNERS', 'CONDITION_RUNTIME_CALLBACK_SHA256'),
                              ('ENTRY_NATIVE_QUERY_OWNERS', 'ENTRY_NATIVE_QUERY_SHA256')):
    owners = getattr(qv, owners_name); digests = getattr(qv, sha_name)
    for name, (address, size) in owners.items():
        body = elf_bytes_at(query_elf, address & ~1, size)
        if sha(body) != digests[name]:
            if query_symbols.get(name, (None, None))[1] != size:
                raise SystemExit('Query owner %s moved or resized; update its pin by hand' % name)
            query_text = query_text.replace(digests[name], sha(body))
            print('query owner seal', name, digests[name][:8], '->', sha(body)[:8])
Path('scripts/verify_overworld_query_code_addon.py').write_text(query_text)

resolver_region = elf_bytes_at(query_elf, qv.RESOLVER_CODE_START, qv.RESOLVER_CODE_END - qv.RESOLVER_CODE_START)
if sha(resolver_region) != qv.RESOLVER_CODE_SHA256:
    query_text = Path('scripts/verify_overworld_query_code_addon.py').read_text()
    Path('scripts/verify_overworld_query_code_addon.py').write_text(query_text.replace(qv.RESOLVER_CODE_SHA256, sha(resolver_region)))
    print('resolver region seal', qv.RESOLVER_CODE_SHA256[:8], '->', sha(resolver_region)[:8])

# 11. Fly-In cost observer: condition Native_Run inside the Query image
fly = Path('tools/overworld/devtools_fly_landing_cost.py'); fly_text = fly.read_text()
run_address, run_size = query_symbols['OverworldConditionNative_Run']
mq = re.search(r"QUERY_NATIVE = \((\d+), (\d+), '([0-9a-f]{64})'\)", fly_text)
assert int(mq.group(1)) + 0x02080000 == run_address & ~1 and int(mq.group(2)) == run_size, 'Native_Run moved'
fly.write_text(fly_text.replace(mq.group(3), sha(elf_bytes_at(query_elf, run_address & ~1, run_size))))

# 12. Query observer: whole-image and package digests
from tools.overworld import devtools_query_observer as qo
elf_bytes = query_elf.read_bytes()
package_blob, _receipt = qo.package(elf_bytes)
qo_path = Path('tools/overworld/devtools_query_observer.py'); qo_text = qo_path.read_text()
qo_text = qo_text.replace(qo.ELF_SHA, sha(elf_bytes)).replace(qo.PACKAGE_SHA, sha(package_blob))
query_image = package_blob[64:64 + _receipt['imageBytes']]
qo_text = qo_text.replace(qo.CARGO_CODE_SHA256, sha(query_image[qo.CARGO_CODE_START:qo.CARGO_CODE_END]))
qo_text = qo_text.replace(qo.CARGO_WILD_SHA256, sha(query_image[qo.CARGO_WILD_START:qo.CARGO_WILD_END]))
qo_path.write_text(qo_text)
print('query observer image/package digests refreshed')

# 13. Any tool pin of the form 'Name': (address, size, 'sha') that names a Query-image function
import glob
tuple_pin = re.compile(r"""(['"])([A-Za-z_][A-Za-z0-9_.]*)\1:\s*\((\d+),\s*(\d+),\s*(['"])([0-9a-f]{64})\5\)""")
for tool in sorted(glob.glob('tools/overworld/*.py') + glob.glob('scripts/*.py')):
    path = Path(tool); text = path.read_text(); changed = False
    def refresh_query_pin(match):
        global changed
        name, address, size, digest = match.group(2), int(match.group(3)), int(match.group(4)), match.group(6)
        entry = query_symbols.get(name)
        if entry is None or (entry[0] & ~1) != (address & ~1) or entry[1] != size:
            return match.group(0)
        fresh = sha(elf_bytes_at(query_elf, address & ~1, size))
        if fresh == digest:
            return match.group(0)
        changed = True
        print('query function pin', tool, name, digest[:8], '->', fresh[:8])
        return match.group(0).replace(digest, fresh)
    new_text = tuple_pin.sub(refresh_query_pin, text)
    if changed:
        path.write_text(new_text)

# 14. Combat observer: behavior-data blob getter body (literal points at the shifted BSS owner)
combat = Path('tools/overworld/devtools_pokemon_combat_observer.py'); combat_text = combat.read_text()
g_address, g_size = table['OverworldWildSpawns_GetBehaviorDataBlob']
g_body = elf_bytes_at(wild, g_address & ~1, g_size)
m_combat = re.search(r'require\(hashlib\.sha256\(blob_getter\[2\]\)\.hexdigest\(\) ==\n\s*"([0-9a-f]{64})"', combat_text)
if m_combat and m_combat.group(1) != sha(g_body):
    combat.write_text(combat_text.replace(m_combat.group(1), sha(g_body)))
    print('combat blob getter seal', m_combat.group(1)[:8], '->', sha(g_body)[:8])
print('resealed')

