"""Execute the actual Thumb packed merge against typed current-layout C data."""
from pathlib import Path
import ast
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'TICKETS.md').is_file())
SOURCE = Path(os.environ.get('PACKED_PROFILE_SOURCE',
    ROOT/'src/player_health_overlay/overworld_walk_input_policy.c'))
BASE = 0x01FFD2CC


def native_assembly(source):
    branch = source.split('#if defined(__arm__)', 1)[1].split('#else', 1)[0]
    branch=branch[branch.index('__asm__('):]
    return ''.join(ast.literal_eval(s) for s in re.findall(r'"(?:[^"\\]|\\.)*"', branch))


def execute(test, code, profile, override, knockback):
    """Bounded interpreter for this one leaf; unknown instructions fail closed."""
    regs = [0x8000+i*4 for i in range(16)]
    regs[0], regs[1], regs[2], regs[13], regs[14] = 0x2000000, 0x2001000, knockback, 0x2004000, 0x1001
    saved = regs[4:12] + [regs[13], regs[14]]
    memory = {BASE+i:b for i,b in enumerate(code)}
    memory.update({regs[0]+i:b for i,b in enumerate(profile)})
    memory.update({regs[1]+i:b for i,b in enumerate(override)})
    memory.update({regs[13]-20+i:0xA5 for i in range(20)})
    def read(address, size):
        test.assertTrue(all(address+i in memory for i in range(size)), 'native read outside packet/code/stack')
        return sum(memory[address+i] << (8*i) for i in range(size))
    def write(address, value, size):
        test.assertTrue(0x2000000<=address<=0x2000000+80-size
            or 0x2004000-20<=address<=0x2004000-size, 'native write outside profile/stack')
        for i in range(size):memory[address+i]=(value>>(8*i))&255
    pc, zero, carry = BASE, False, False
    for _ in range(600):
        address=pc;op=read(pc,2);pc+=2
        rd,rn=op&7,(op>>3)&7;kind=op&0xF800
        if op in (0xB5F0,0xBDF0):
            if op==0xB5F0:
                regs[13]-=20
                for i,r in enumerate((4,5,6,7,14)):write(regs[13]+4*i,regs[r],4)
            else:
                for i,r in enumerate((4,5,6,7,15)):regs[r]=read(regs[13]+4*i,4)
                regs[13]+=20
                test.assertEqual(regs[15],0x1001)
                test.assertEqual(regs[4:12]+[regs[13],regs[14]],saved)
                return bytes(memory[0x2000000+i] for i in range(80))
        elif op&0xFC00==0x4400:
            test.assertEqual((op>>8)&3,2) # MOV high-register, including ip.
            regs[(op&7)|((op>>4)&8)]=regs[(op>>3)&15]
        elif kind==0xA000:
            regs[(op>>8)&7]=((address+4)&~3)+((op&255)<<2)
        elif kind in (0x6800,0x7800):
            size=4 if kind==0x6800 else 1
            regs[rd]=read(regs[rn]+((op>>6)&31)*size,size)
        elif op&0xFE00 in (0x5C00,0x5400):
            effective=regs[rn]+regs[(op>>6)&7]
            if op&0xFE00==0x5C00:regs[rd]=read(effective,1)
            else:write(effective,regs[rd],1)
        elif kind in (0x2000,0x2800,0x3000,0x3800):
            r=(op>>8)&7;value=op&255
            if kind==0x2000:regs[r]=value;zero=value==0
            elif kind==0x2800:zero=regs[r]==value;carry=regs[r]>=value
            elif kind==0x3000:regs[r]=(regs[r]+value)&0xFFFFFFFF;zero=regs[r]==0
            else:carry=regs[r]>=value;regs[r]=(regs[r]-value)&0xFFFFFFFF;zero=regs[r]==0
        elif kind==0:
            shift=(op>>6)&31;value=regs[rn]
            if shift:carry=bool(value&(1<<(32-shift)))
            regs[rd]=(value<<shift)&0xFFFFFFFF;zero=regs[rd]==0
        elif op&0xFC00==0x4000:
            operation=(op>>6)&15
            if operation==3:
                shift=regs[rn]&255;value=regs[rd]
                if shift:carry=bool(value&(1<<(shift-1))) if shift<=32 else False
                regs[rd]=value>>shift if shift<32 else 0
            elif operation==0:regs[rd]&=regs[rn]
            elif operation==1:regs[rd]^=regs[rn]
            else:test.fail(f'unexpected native ALU instruction {op:04x}')
            zero=regs[rd]==0
        elif op&0xF000==0xD000:
            condition=(op>>8)&15
            test.assertIn(condition,(0,1,3,9))
            taken={0:zero,1:not zero,3:not carry,9:not carry or zero}[condition]
            if taken:pc=address+4+((op&255)-(256 if op&128 else 0))*2
        elif kind==0xE000:
            offset=(op&2047)-(2048 if op&1024 else 0);pc=address+4+offset*2
        else:test.fail(f'unexpected native packed instruction {op:04x}')
    test.fail('native packed merge did not return within its fixed work bound')


class NativePackedProfileAbiTests(unittest.TestCase):
    def test_actual_native_merge_matches_current_typed_layout_and_rejects_old_offsets(self):
        assembly=native_assembly(SOURCE.read_text())
        authored=json.loads((ROOT/'data/overworld_behavior_profiles.json').read_text())
        throw=next(p for p in authored['profiles'] if p['id']=='throw')
        action=throw['fields']['onReachAction']['value']
        self.assertEqual(action,'OW_WILD_BEHAVIOR_ON_REACH_PICKUP_CONDITION_ACTOR')
        program=r'''
#define OVERWORLD_BEHAVIOR_HOST
#include "overworld_behavior_packed_options.h"
#include <stddef.h>
#include <stdio.h>
#include <string.h>
_Static_assert(offsetof(OverworldWildBehaviorOverrideProfile,mask2)==28,"mask2");
_Static_assert(offsetof(OverworldWildBehaviorOverrideProfile,mask3)==32,"mask3");
_Static_assert(offsetof(OverworldWildBehaviorOverrideProfile,profile)==36,"profile");
_Static_assert(sizeof(OverworldWildBehaviorOverrideProfile)==232,"override");
static void emit(OverworldWildBehaviorProfileData p,OverworldWildBehaviorOverrideProfile o,u32 k){
 OverworldWildBehaviorProfileData result=p;
 OverworldBehaviorPackedOptions_ApplyInline(&result,&o,k);
 fwrite(&p,80,1,stdout);fwrite(&o,232,1,stdout);fwrite(&k,4,1,stdout);fwrite(&result,80,1,stdout);
}
int main(void){
 OverworldWildBehaviorProfileData p={0};OverworldWildBehaviorOverrideProfile o={0};
 o.mask2=OW_WILD_BEHAVIOR_OVERRIDE2_ON_REACH_ACTION;
 o.profile.onReachAction=AUTHORED_ACTION;emit(p,o,0);
 for(unsigned pattern=0;pattern<2;pattern++)for(unsigned bit=0;bit<=64;bit++)for(unsigned k=0;k<4;k++){
  memset(&p,pattern?0xA5:0x5A,sizeof(p));memset(&o,pattern?0x3C:0xC3,sizeof(o));
  o.mask=0;o.mask2=bit>=1&&bit<=32?(1u<<(bit-1)):0;
  o.mask3=bit>=33?(1u<<(bit-33)):0;
  emit(p,o,k==0?0:k==1?3:k==2?28:224);
 }
 return ferror(stdout)?1:0;
}
'''.replace('AUTHORED_ACTION',action)
        with tempfile.TemporaryDirectory(prefix='native-packed-abi-') as directory:
            folder=Path(directory);(folder/'leaf.s').write_text(assembly)
            assembler=shutil.which('arm-none-eabi-as');linker=shutil.which('arm-none-eabi-ld')
            objcopy=shutil.which('arm-none-eabi-objcopy')
            self.assertTrue(assembler and linker and objcopy,'native ARM tools are required')
            subprocess.run([assembler,'-mthumb','-mcpu=arm946e-s',str(folder/'leaf.s'),'-o',str(folder/'leaf.o')],check=True,capture_output=True)
            (folder/'leaf.ld').write_text('SECTIONS { . = 0x01FFD2CC; .leaf : { *(.overworld_behavior_packed_options) } ASSERT(SIZEOF(.leaf) <= 106,"fixed packed slot") /DISCARD/ : { *(.text) *(.data) *(.bss) } }')
            subprocess.run([linker,'-T',str(folder/'leaf.ld'),str(folder/'leaf.o'),'-o',str(folder/'leaf.elf')],check=True,capture_output=True)
            subprocess.run([objcopy,'-O','binary','-j','.leaf',str(folder/'leaf.elf'),str(folder/'leaf.bin')],check=True,capture_output=True)
            image=(folder/'leaf.bin').read_bytes();self.assertLessEqual(len(image),106)
            symbols=subprocess.run([shutil.which('arm-none-eabi-objdump'),'-t',str(folder/'leaf.elf')],check=True,capture_output=True,text=True).stdout
            self.assertRegex(symbols,r'01ffd2cc\s+g\s+F\s+\.leaf\s+00000067\s+OverworldBehaviorPackedOptions_Apply')
            code=image[:103];self.assertEqual(len(code),103);self.assertFalse(any(image[103:]))
            compiled=subprocess.run(['cc','-std=c11','-I',str(ROOT/'include'),'-x','c','-','-o',str(folder/'packets')],input=program,text=True,capture_output=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            result=subprocess.run([str(folder/'packets')],check=True,capture_output=True).stdout
        self.assertEqual(len(result),521*396)
        packets=[result[i:i+396] for i in range(0,len(result),396)]
        self.assertEqual(packets[0][316+75],1,'typed authored pickup must stay on')
        for i,row in enumerate(packets):
            with self.subTest(packet=i):
                self.assertEqual(execute(self,code,row[:80],row[80:312],struct.unpack_from('<I',row,312)[0]),row[316:])
        # Every stale operand, separately, must break the same typed packets.
        for offset,old in ((0x12,24),(0x1A,28),(0x24,32)):
            stale=bytearray(code);op=struct.unpack_from('<H',stale,offset)[0]
            op=(op&~0x7C0)|((old//4)<<6) if offset!=0x24 else (op&0xFF00)|old
            struct.pack_into('<H',stale,offset,op)
            self.assertTrue(any(execute(self,stale,row[:80],row[80:312],struct.unpack_from('<I',row,312)[0])!=row[316:] for row in packets),f'old operand at {offset:x} passed')


if __name__=='__main__':unittest.main()
