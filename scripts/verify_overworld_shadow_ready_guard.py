#!/usr/bin/env python3
"""Execute the authentic circle-shadow Thumb callbacks and exact ready seam.

This follows the bounded instruction-level grass/bubble guard checks. Only
native external callback results are supplied. No game or ROM build runs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
SITE = 0x021FDD8A
SHIFT = bytes.fromhex('400e')  # Actual Thumb LSR r0,r0,#25; packaged bytes are checked separately.
ORIGINAL = bytes.fromhex('0120')
OWNERS = {
    'initialize': (0x021FDD48, 76, 'b24bab80e16e968b5214bfeff51b655c58fcdeda4162d08820deaeaabb9a102e'),
    'update': (0x021FDB44, 136, '926209d0300742589d8f0c9fc9c6a26b66fbd6cfc3e65caaff5bd26b16e15f1e'),
    'draw': (0x021FDBCC, 176, 'aeb56f8f346e4ffbb86f9237a63d60d1c3cba276bfd03f3b7dd11b1d1ccc688d'),
    'destroy': (0x021FDB34, 16, '07a83cd8f25e4ab0236ed55cf2f2d72901d18cd40f210d3b93ef26b840d26a0e'),
}
MODEL = 0x02280000
MAIN_MODEL_POINTERS = (0x02000000, 0x02000004, MODEL, 0x023FFFFC)


def check(value, message):
    if not value:
        raise ValueError(message)


def read_blocks(rom_path):
    import ndspy.code
    import ndspy.rom
    rom = ndspy.rom.NintendoDSRom.fromFile(rom_path)
    overlay = ndspy.code.loadOverlayTable(rom.arm9OverlayTable,
        lambda _id, file_id: rom.files[file_id], {1})[1]
    check(overlay.ramAddress == 0x021E5900, 'circle shadow overlay owner differs')
    return {name: bytes(overlay.data[address-overlay.ramAddress:address-overlay.ramAddress+size])
            for name, (address, size, _) in OWNERS.items()}


def authenticate(blocks, ready_instruction=ORIGINAL):
    check(set(blocks) == set(OWNERS), 'circle shadow callback inventory differs')
    offset = SITE - OWNERS['initialize'][0]
    for name, (_, size, digest) in OWNERS.items():
        body = blocks[name]
        check(len(body) == size, 'circle shadow ' + name + ' extent differs')
        if name == 'initialize':
            check(body[offset:offset+2] == ready_instruction, 'circle shadow ready instruction differs')
            check(body[offset-2:offset] == bytes.fromhex('6062')
                  and body[offset+2:offset+4] == bytes.fromhex('e060'),
                  'circle shadow model/ready stores differ')
            body = body[:offset] + ORIGINAL + body[offset+2:]
        check(hashlib.sha256(body).hexdigest() == digest,
              'circle shadow ' + name + ' full body differs')


def source_guard():
    source = (ROOT/'armips/asm/overworld_wild_shadow.s').read_text()
    matches = re.findall(r'^\.org\s+0x021FDD8A\s*\n\s*([^\n]+)', source, re.M)
    check(matches == ['lsr r0, r0, 25'], 'circle shadow armips ready seam differs')
    # The bounded pointer conversion applies only to the native main-RAM model owner.
    reference = (ROOT/'.codex-reference/pokeheartgold/asm/overlay_01_021FDA14.s').read_text()
    initialize = reference.split('ov01_021FDD48: ;', 1)[1].split('thumb_func_end ov01_021FDD48', 1)[0]
    check('bl ov01_021F16EC\n\tstr r0, [r4, #0x24]\n\tmov r0, #1\n\tstr r0, [r4, #0xc]' in initialize,
          'circle shadow reference allocation/ownership seam differs')


def candidate_blocks(stock):
    authenticate(stock)
    result = dict(stock)
    offset = SITE - OWNERS['initialize'][0]
    result['initialize'] = stock['initialize'][:offset] + SHIFT + stock['initialize'][offset+2:]
    authenticate(result, SHIFT)
    return result


class ShadowCallbacks:
    """Bounded Thumb interpreter, with typed native call seams and owned words."""
    def __init__(self, blocks, allocations):
        self.blocks = blocks
        self.image = {address+i:b for name, (address, _, _) in OWNERS.items()
                      for i,b in enumerate(blocks[name])}
        self.data, self.object, self.effect = 0x02200000, 0x02210000, 0x02220000
        self.manager, self.resource = 0x02230000, 0x02240000
        self.memory = {self.data+i:0 for i in range(0, 0x38, 4)}
        self.memory.update({self.data:224, self.data+4:33, self.data+8:23,
                            self.data+0x18:self.resource, self.data+0x20:self.object,
                            self.data+0x28:0x1000, self.data+0x34:0x40})
        self.allocations = list(allocations)
        self.owned = set()
        self.allocations_used, self.model_operations, self.frees = 0, [], []
        self.calls, self.writes = [], []

    @property
    def ready(self):
        return self.memory[self.data+0xC]

    @property
    def model(self):
        return self.memory[self.data+0x24]

    def word(self, address):
        check(address in self.memory, f'circle shadow unowned word read {address:08X}')
        return self.memory[address]

    def store(self, address, value):
        self.memory[address] = value & 0xFFFFFFFF
        self.writes.append(address)

    def external(self, address, regs):
        self.calls.append(address)
        if address == 0x0205F35C:  # MapObject_GetManager
            check(regs[0] == self.object, 'circle shadow object manager argument differs')
            result = self.manager
        elif address == 0x021F9744:  # Native model resource eligibility.
            check(regs[0] == self.manager and regs[1] == self.memory[self.data+8],
                  'circle shadow model eligibility arguments differ')
            result = 1
        elif address == 0x021FA2D4:
            check(regs[0] == self.object, 'circle shadow object eligibility differs')
            result = 0
        elif address == 0x021F18F0:
            check(regs[0] == self.resource and regs[1] == 2, 'circle shadow resource arguments differ')
            result = self.resource + 4
        elif address in (0x02068DB8, 0x02068DA8):
            check(regs[0] == self.effect, 'circle shadow position callback owner differs')
            if address == 0x02068DB8:
                for i in range(3): self.store(regs[1]+i*4, 0)
            result = 0
        elif address == 0x021F16EC:
            check(regs[0] == self.resource and regs[1] == regs[13]
                  and regs[2] == regs[13]+0x28, 'circle shadow allocation ABI differs')
            check(self.allocations, 'circle shadow exceeded bounded allocation attempts')
            result = self.allocations.pop(0)
            check(result == 0 or 0x02000000 <= result < 0x02400000 and result & 3 == 0,
                  'circle shadow model outside native main-RAM allocation range')
            self.allocations_used += 1
            if result: self.owned.add(result)
        elif address == 0x0205F25C:
            check(regs[0] == self.object, 'circle shadow sprite owner differs')
            result = self.memory[self.data+8]
        elif address == 0x0205F0A8:
            check(regs[0] == self.object and regs[1] == self.memory[self.data]
                  and regs[2] == self.memory[self.data+4], 'circle shadow object identity differs')
            result = 1
        elif address == 0x0205F870:
            check(regs[0] == self.object, 'circle shadow live-object flag owner differs')
            result = 1
        elif address == 0x021FDC7C:
            check(regs[0] == self.data and regs[1] == self.object,
                  'circle shadow update geometry arguments differ')
            for i in range(3): self.store(regs[2]+i*4, 0)
            result = 0
        elif address == 0x0205F96C:
            check(regs[0] == self.object, 'circle shadow facing vector owner differs')
            for i in range(3): self.store(regs[1]+i*4, 0)
            result = 0
        elif address == 0x0205F684:
            check(regs[0] == self.object, 'circle shadow visibility owner differs')
            result = 0
        elif address in (0x02023EA4, 0x02023E50, 0x02023E78, 0x02023EE0, 0x02023F1C):
            check(regs[0] != 0 and regs[0] in self.owned and regs[0] == self.model
                  and self.ready == 1, 'circle shadow touched a NULL/unowned model or nonexact ready flag')
            self.model_operations.append((address, regs[0]))
            result = 0
        elif address == 0x021F72DC:
            check(regs[0] == self.object, 'circle shadow sprite presentation owner differs')
            result = 0
        elif address in (0x02023EF4, 0x02023F30):
            result = 0
        elif address == 0x02023DA4:
            check(regs[0] != 0 and regs[0] in self.owned and regs[0] == self.model
                  and self.ready == 1, 'circle shadow freed a NULL/unowned model or nonexact ready flag')
            self.frees.append(regs[0]); self.owned.remove(regs[0]); result = 0
        else:
            raise ValueError(f'circle shadow unexpected native call {address:08X}')
        # Native callbacks may clobber all caller-save registers/flags.
        regs[0:4] = [result, 0xDEAD0001, 0xDEAD0002, 0xDEAD0003]

    def run(self, name):
        regs = [0x11000000+i*4 for i in range(16)]
        regs[0], regs[1], regs[13], regs[14], regs[15] = self.effect, self.data, 0x023F0000, 0x02001001, OWNERS[name][0]
        original = regs[:]; compare = (0, 0)
        def signed(n): return n-(1<<32) if n & 0x80000000 else n
        for _ in range(256):
            pc = regs[15]
            if pc == original[14] & ~1:
                check(regs[4:13] == original[4:13] and regs[13] == original[13],
                      'circle shadow callback changed saved registers/stack')
                return
            check(pc in self.image and pc+1 in self.image, f'circle shadow unowned instruction {pc:08X}')
            op = self.image[pc] | self.image[pc+1]<<8; regs[15] = pc+2
            if op & 0xF800 == 0xF000:
                second = self.image[pc+2] | self.image[pc+3]<<8
                check(second & 0xF800 == 0xF800, 'circle shadow native BL encoding differs')
                displacement = ((op & 0x7FF)<<12) | ((second & 0x7FF)<<1)
                if displacement & (1<<22): displacement -= 1<<23
                target = pc+4+displacement; regs[14] = (pc+4)|1
                if target == OWNERS['initialize'][0]: regs[15] = target
                else: self.external(target, regs); regs[15] = pc+4
            elif op & 0xFE00 in (0xB400, 0xBC00):
                selected = [i for i in range(8) if op & 1<<i] + ([14 if op & 0xFE00 == 0xB400 else 15] if op & 256 else [])
                if op & 0xFE00 == 0xB400:
                    regs[13] -= len(selected)*4
                    for i,r in enumerate(selected): self.store(regs[13]+i*4, regs[r])
                else:
                    sp = regs[13]
                    for i,r in enumerate(selected): regs[r] = self.word(sp+i*4)
                    regs[13] += len(selected)*4; regs[15] &= ~1
            elif op & 0xFF00 == 0xB000:
                regs[13] += (op & 127) * (-4 if op & 128 else 4)
            elif op & 0xF800 in (0x2000, 0x2800):
                reg = (op>>8)&7
                if op & 0xF800 == 0x2000: regs[reg] = op & 255
                else: compare = (regs[reg], op & 255)
            elif op & 0xF800 in (0x0000, 0x0800):
                value = regs[(op>>3)&7]; shift = (op>>6)&31
                regs[op&7] = ((value<<shift)&0xFFFFFFFF) if op & 0xF800 == 0 else (value>>(shift or 32))
            elif op & 0xF800 in (0x6000, 0x6800):
                address = regs[(op>>3)&7] + ((op>>6)&31)*4
                if op & 0xF800 == 0x6800: regs[op&7] = self.word(address)
                else: self.store(address, regs[op&7])
            elif op & 0xF800 in (0x9000, 0x9800):
                address = regs[13]+(op&255)*4
                if op & 0xF800 == 0x9800: regs[(op>>8)&7] = self.word(address)
                else: self.store(address, regs[(op>>8)&7])
            elif op & 0xF800 == 0xA800:
                regs[(op>>8)&7] = regs[13]+(op&255)*4
            elif op & 0xF800 == 0x1800:
                left = regs[(op>>3)&7]; right = ((op>>6)&7) if op & 0x400 else regs[(op>>6)&7]
                regs[op&7] = (left-right if op & 0x200 else left+right)&0xFFFFFFFF
            elif op & 0xF800 == 0x3000:
                reg = (op>>8)&7; regs[reg] = (regs[reg]+(op&255))&0xFFFFFFFF
            elif op & 0xFFC0 == 0x4280:
                compare = (regs[op&7], regs[(op>>3)&7])
            elif op & 0xFFC0 == 0x4240:
                regs[op&7] = (-regs[(op>>3)&7])&0xFFFFFFFF
            elif op & 0xF000 == 0xD000 and op & 0xF00 != 0xF00:
                cond=(op>>8)&15;a,b=compare
                take={0:a==b,1:a!=b,11:signed(a)<signed(b),12:signed(a)>signed(b)}
                check(cond in take, 'circle shadow unexpected conditional branch')
                if take[cond]: regs[15] = pc+4+((op&255)-(256 if op&128 else 0))*2
            elif op & 0xF800 == 0xE000:
                offset=op&0x7FF
                if offset&0x400:offset-=0x800
                regs[15]=pc+4+offset*2
            elif op == 0x46C0:  # Authentic Thumb NOP used only by a copied removed-store control.
                pass
            else:
                raise ValueError(f'circle shadow unexpected instruction {op:04X} at {pc:08X}')
        raise ValueError('circle shadow callback exceeded256 instructions')


def verify_lifecycle(blocks, pointer=MODEL):
    callbacks = ShadowCallbacks(blocks, [0, 0, pointer])
    for owner in ('initialize', 'update'):
        callbacks.run(owner)
        check(callbacks.ready == callbacks.model == 0 and not callbacks.owned,
              'failed circle shadow admission created readiness/ownership')
        callbacks.run('draw')
        check(not callbacks.model_operations and not callbacks.frees,
              'NULL circle shadow reached model draw/free')
    null_owner = ShadowCallbacks(blocks, [0])
    null_owner.run('initialize'); null_owner.run('destroy')
    check(null_owner.ready == null_owner.model == 0 and not null_owner.frees,
          'NULL circle shadow owner destructor reached model free')
    callbacks.run('update')
    check(callbacks.allocations_used == 3 and callbacks.ready == 1
          and callbacks.model == pointer and callbacks.owned == {pointer},
          'circle shadow retry did not establish exact model ownership/ready1')
    callbacks.run('update')
    check(callbacks.allocations_used == 3, 'ready circle shadow allocated again')
    callbacks.run('draw')
    check(len(callbacks.model_operations) == 5 and all(p == pointer for _,p in callbacks.model_operations),
          'ready circle shadow did not use its exact owned model')
    callbacks.run('destroy')
    check(callbacks.frees == [pointer] and not callbacks.owned,
          'circle shadow owner destructor did not free its model exactly once')
    return dict(allocationAttempts=3,failedAttempts=2,ready=callbacks.ready,
                modelOperations=len(callbacks.model_operations),frees=len(callbacks.frees),nullModelFreeCalls=len(null_owner.frees))


def verify(blocks):
    authenticate(blocks, SHIFT)
    cases = [verify_lifecycle(blocks, pointer) for pointer in MAIN_MODEL_POINTERS]
    offset = SITE-OWNERS['initialize'][0]
    rejected = []
    for name, at, replacement in (
        ('stock-mov1', offset, ORIGINAL),
        ('wrong-shift24', offset, bytes.fromhex('000e')),
        ('skip-ready-store', offset+2, bytes.fromhex('c046')),
    ):
        changed = dict(blocks); body = blocks['initialize']; changed['initialize'] = body[:at]+replacement+body[at+2:]
        try: verify_lifecycle(changed)
        except ValueError: rejected.append(name)
        else: raise ValueError('circle shadow copied fault was accepted: '+name)
    return dict(cases=cases,copiedFaultsRejected=rejected,gameBehaviorVerified=False,
                limits='NULL or native main-RAM model pointers only; one owner destructor call. External eligibility and allocation returns are typed host seams.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom',type=Path,help='also require the published exact LSR25 seam and all unchanged native callbacks')
    args=parser.parse_args()
    source_guard(); stock=read_blocks(ROOT/'rom.nds'); authenticate(stock)
    blocks=candidate_blocks(stock)
    if args.rom:
        blocks=read_blocks(args.rom);authenticate(blocks,SHIFT)
    report=verify(blocks)
    report.update(passed=True,scope='published-shadow-ready-block' if args.rom else 'copied-stock-block-candidate',
                  ownerSha256={name:hashlib.sha256(body).hexdigest() for name,body in blocks.items()})
    print(json.dumps(report,sort_keys=True))


if __name__=='__main__':main()
