"""Native walking friendship semantics, stack ownership and package boundaries.

The old C-only stub test could not execute the naked continuation bridge. Its
replacement assembles the current source and executes that Thumb plus the
hash-checked ARM9 body from current test.nds, with explicit deterministic
data/item/RNG/lock leaves. The extracted build/arm9.bin precedes ARMIPS edits.
It proves behavior and ABI; it does not prove game speed.
"""
from pathlib import Path
import ast
from copy import deepcopy
import hashlib
import re
import shutil
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, arm_const as A
from scripts import verify_pokemon_move_history_capture as package_gate
from scripts import verify_no_item_data as item_gate

ROOT=Path(__file__).resolve().parents[2]
BASE=0x023CCF90;STOP=0x1000;STACK=0x03002000;MON=0x03004000
ARM9=OLD=NEW=b''
MD=Cs(CS_ARCH_ARM,CS_MODE_THUMB);MD.detail=True
MASK=0xFFFFFFFF

# The old authored three-call adapter is a copied minimum-work fault too.
# This assembly is the previous hg-engine wrapper, not copied stock ROM data.
BASELINE_ASSEMBLY=r'''
.syntax unified
.thumb
.global WalkingFriendship_Acquire
.thumb_func
.thumb_set WalkingFriendship_Acquire, 0x0206DD40
.global WalkingFriendship_Apply
.thumb_func
.thumb_set WalkingFriendship_Apply, 0x0206FE90
.global WalkingFriendship_Release
.thumb_func
.thumb_set WalkingFriendship_Release, 0x0206DD8C
.section .walking_friendship,"ax",%progbits
.global OverworldField_ApplyWalkingFriendship
.type OverworldField_ApplyWalkingFriendship,%function
.thumb_func
OverworldField_ApplyWalkingFriendship:
 push {r3-r7,lr}
 movs r4,r0
 movs r6,r1
 movs r7,r2
 bl WalkingFriendship_Acquire
 movs r5,r0
 movs r2,r7
 movs r1,r6
 movs r0,r4
 bl WalkingFriendship_Apply
 movs r1,r5
 movs r0,r4
 bl WalkingFriendship_Release
 pop {r3-r7,pc}
.size OverworldField_ApplyWalkingFriendship,.-OverworldField_ApplyWalkingFriendship
'''


def native_assembly(source):
    """Assemble the two actual source asm blocks, without a host C substitute."""
    aliases=source.split('__asm__(',1)[1].split(');',1)[0]
    body=source.split('__asm__ volatile(',1)[1].split(');',1)[0]
    strings=lambda text:''.join(ast.literal_eval(s) for s in re.findall(r'"(?:[^"\\]|\\.)*"',text))
    return strings(aliases)+'\n.section .walking_friendship,"ax",%progbits\n.global OverworldField_ApplyWalkingFriendship\n.type OverworldField_ApplyWalkingFriendship,%function\n.thumb_func\nOverworldField_ApplyWalkingFriendship:\n'+strings(body)+'\n.size OverworldField_ApplyWalkingFriendship,.-OverworldField_ApplyWalkingFriendship\n'


def signed(v,bits=32):
    return v-(1<<bits) if v&(1<<(bits-1)) else v


class Machine:
    def __init__(self,code,mon,kind,location,seed,locked,*,strict_new=False):
        self.code=code;self.mon=deepcopy(mon);self.kind=kind;self.location=location
        self.seed=seed;self.locked=locked;self.initial_locked=locked
        self.r=[0xA5000100+4*i for i in range(16)]
        self.r[0:3]=[MON,kind,location];self.r[13]=STACK;self.r[14]=STOP|1
        self.saved=self.r[4:12];self.stack={};self.pc=BASE;self.flags=(False,False,False,False)
        self.calls=[];self.acquired=0;self.released=0;self.continuations=0
        self.strict_new=strict_new;self.instructions=0

    def read(self,address,size):
        if BASE<=address and address+size<=BASE+len(self.code):raw=self.code[address-BASE:address-BASE+size]
        elif 0x02000000<=address and address+size<=0x02000000+len(ARM9):raw=ARM9[address-0x02000000:address-0x02000000+size]
        else:
            assert STACK-128<=address<=STACK-size,('unowned read',address,size)
            assert all(address+i in self.stack for i in range(size)),('uninitialized stack',address,size)
            raw=bytes(self.stack[address+i] for i in range(size))
        return int.from_bytes(raw,'little')

    def write(self,address,value,size):
        assert STACK-128<=address<=STACK-size,('unowned write',address,size)
        for i in range(size):self.stack[address+i]=(value>>(8*i))&255

    def reg(self,number):
        name=MD.reg_name(number)
        return {'sp':13,'lr':14,'pc':15,'ip':12,'sb':9,'sl':10,'fp':11}.get(name,
            int(name[1:]) if name.startswith('r') else -1)

    def value(self,operand,pc):
        if operand.type==A.ARM_OP_IMM:return operand.imm&MASK
        assert operand.type==A.ARM_OP_REG
        n=self.reg(operand.reg)
        return (pc+4)&MASK if n==15 else self.r[n]

    def address(self,operand,pc):
        assert operand.type==A.ARM_OP_MEM
        m=operand.mem;n=self.reg(m.base)
        value=((pc+4)&~3) if n==15 else self.r[n]
        if m.index:value+=self.r[self.reg(m.index)]
        return (value+m.disp)&MASK

    def nz(self,result):
        _,_,c,v=self.flags;self.flags=(bool(result&0x80000000),result==0,c,v)

    def condition(self,cc):
        n,z,c,v=self.flags
        return {A.ARM_CC_AL:True,A.ARM_CC_INVALID:True,A.ARM_CC_EQ:z,A.ARM_CC_NE:not z,
            A.ARM_CC_LT:n!=v,A.ARM_CC_LE:z or n!=v,A.ARM_CC_GE:n==v,
            A.ARM_CC_GT:not z and n==v,A.ARM_CC_HS:c,A.ARM_CC_LO:not c}[cc]

    def external(self,target):
        r=self.r;result=None
        if target==0x0201FD44:
            self.seed=(self.seed*0x41C64E6D+0x6073)&MASK
            result=self.seed>>16;self.calls.append(('rng',self.seed,result))
        elif target==0x0206DD40:
            assert r[0]==MON;result=int(not self.locked);self.locked=True;self.acquired+=1
        elif target==0x0206DD8C:
            assert r[0]==MON and r[1]==int(not self.initial_locked),('wrong release token',r[1])
            self.locked=self.initial_locked;self.released+=1;result=r[1]
        elif target==0x0206E540:
            assert r[0]==MON and r[2]==0 and self.locked
            attr=r[1];self.calls.append(('get',attr));result=self.mon[attr]
        elif target==0x02077D88:
            assert r[1:3]==[1,0]
            self.calls.append(('item',r[0],r[1],r[2]));result=53 if r[0] else 0
        elif target==0x0206EC40:
            assert r[0]==MON and r[1]==9 and self.locked
            result=self.read(r[2],2);self.mon[9]=result;self.calls.append(('set',9,result))
        elif target==0x020F2998:
            assert r[1]!=0;result=int(signed(r[0])/signed(r[1]))&MASK
        else:return False
        # All external leaves keep the ABI's callee-saved registers. Poison
        # volatile arguments so an accidental use after BL cannot pass.
        r[0]=result;r[1:4]=[0xDEAD0001,0xDEAD0002,0xDEAD0003];r[12]=0xDEAD000C
        self.pc=r[14]&~1
        return True

    def run(self):
        while self.pc!=STOP:
            self.instructions+=1;assert self.instructions<600,('native instruction bound',self.pc)
            assert self.r[13]%8==0 or self.pc not in (0x0201FD44,0x0206DD40,0x0206DD8C)
            if self.external(self.pc):continue
            pc=self.pc
            if pc==0x0206FEA8:
                self.continuations+=1
                assert self.r[5:7]==[MON,self.kind],('stock saved registers',self.r[5:7])
                assert self.read(self.r[13],4)==self.location,'stock location frame differs'
                assert self.r[13]==STACK-24-32,'stock frame must be its exact32 bytes'
            opcode=self.read(pc,2)
            raw=struct.pack('<H',opcode)
            if opcode&0xF800==0xF000:raw+=struct.pack('<H',self.read(pc+2,2))
            ins=next(MD.disasm(raw,pc,count=1));self.pc=pc+ins.size
            if not self.condition(ins.cc):continue
            op=ins.mnemonic.split('.')[0];args=ins.operands;r=self.r
            if op in ('push','pop'):
                ids=[self.reg(a.reg) for a in args]
                if op=='push':
                    values=[r[n] for n in ids];r[13]-=4*len(ids)
                    for i,v in enumerate(values):self.write(r[13]+4*i,v,4)
                else:
                    values=[self.read(r[13]+4*i,4) for i in range(len(ids))];r[13]+=4*len(ids)
                    for n,v in zip(ids,values):
                        if n==15:self.pc=v&~1
                        else:r[n]=v
            elif op in ('mov','movs'):
                v=self.value(args[1],pc);r[self.reg(args[0].reg)]=v
                if ins.update_flags:self.nz(v)
            elif op in ('add','adds','sub','subs','cmp'):
                n=self.reg(args[0].reg);left=r[n] if len(args)==2 else self.value(args[1],pc)
                right=self.value(args[-1],pc);minus=op.startswith('sub') or op=='cmp'
                value=(left-right if minus else left+right)&MASK
                if op!='cmp':r[n]=value
                if ins.update_flags or op=='cmp':
                    carry=left>=right if minus else left+right>MASK
                    overflow=bool(((left^right)&(left^value))&0x80000000) if minus else bool((~(left^right)&(left^value))&0x80000000)
                    self.flags=(bool(value&0x80000000),value==0,carry,overflow)
            elif op in ('lsl','lsls','lsr','lsrs','asr','asrs'):
                n=self.reg(args[0].reg);value=r[n] if len(args)==2 else self.value(args[1],pc)
                count=self.value(args[-1],pc)
                if op.startswith('lsl'):result=(value<<count)&MASK;carry=bool(value&(1<<(32-count))) if count else self.flags[2]
                elif op.startswith('asr'):result=(signed(value)>>count)&MASK;carry=bool(value&(1<<(count-1))) if count else self.flags[2]
                else:result=value>>count;carry=bool(value&(1<<(count-1))) if count else self.flags[2]
                r[n]=result
                if ins.update_flags:self.flags=(bool(result&0x80000000),result==0,carry,self.flags[3])
            elif op=='tst':self.nz(self.value(args[0],pc)&self.value(args[1],pc))
            elif op in ('mul','muls'):
                n=self.reg(args[0].reg);r[n]=(self.value(args[-2],pc)*self.value(args[-1],pc))&MASK
                if ins.update_flags:self.nz(r[n])
            elif op in ('ldr','ldrh','ldrsh','ldrsb','str','strh'):
                n=self.reg(args[0].reg);address=self.address(args[1],pc);size=1 if op=='ldrsb' else 2 if op in ('ldrh','ldrsh','strh') else 4
                if op.startswith('str'):self.write(address,r[n],size)
                else:
                    value=self.read(address,size);r[n]=signed(value,size*8)&MASK if op in ('ldrsh','ldrsb') else value
            elif op in ('b','beq','bne','blt','ble','bge','bgt','bhs','blo'):
                self.pc=args[0].imm&~1
            elif op in ('bl','blx'):
                r[14]=(pc+ins.size)|1;self.pc=self.value(args[0],pc)&~1
            elif op=='bx':self.pc=self.value(args[0],pc)&~1
            elif op=='nop':pass
            else:raise AssertionError(('unexpected Thumb instruction',pc,op,ins.op_str))
        assert self.r[4:12]==self.saved,'callee-saved register changed'
        assert self.r[13]==STACK,'caller stack not restored'
        assert self.locked==self.initial_locked,'caller lock changed'
        assert self.acquired==self.released,'unpaired lock'
        if self.strict_new:
            selected=self.kind!=5 or (self.calls[0][2]&1)==0
            assert self.acquired==int(selected),'unselected walking member took a data lock'
        return {'mon':self.mon,'seed':self.seed,'calls':self.calls,'locked':self.locked,
            'acquired':self.acquired,'released':self.released,'continuations':self.continuations,
            'instructions':self.instructions}


def check(code,mon,kind,location,seed,locked):
    old=Machine(OLD,mon,kind,location,seed,locked).run()
    new=Machine(code,mon,kind,location,seed,locked,strict_new=True).run()
    assert all(old[k]==new[k] for k in ('mon','seed','calls','locked')),'stock result/RNG/item rule differs'
    assert sum(c[0]=='rng' for c in new['calls'])==int(kind==5)
    return old,new


def native_results():
    assert len(NEW)==68 and BASE+len(NEW)<=0x023CCFD8
    cases=[]
    for seed in (0,1,0x12345678,0x89ABCDEF):
        for locked in (False,True):
            for kind in (5,4):
                for friendship in (0,99,100,199,200,254,255):
                    for item,ball,location in ((0,4,127),(1,11,127),(0,11,9)):
                        mon={174:56,6:item,9:friendship,180:ball,152:127}
                        cases.append((mon,kind,location,seed,locked))
    for species in (0,494):
        cases.append(({174:species,6:0,9:70,180:4,152:127},5,127,0,False))
    results=[check(NEW,*case) for case in cases]
    # One six-member batch checks seed handoff between successive members.
    seed=0x12345678;batch=[]
    for i in range(6):
        old,new=check(NEW,{174:56+i,6:0,9:70,180:4,152:127},5,127,seed,False)
        seed=new['seed'];batch.append({'selected':bool(new['acquired']),'seed':seed})
    faults={}
    for name,mutate in (
        ('old-lock-before-rng',lambda b:OLD),
        ('inverted-walking-result',lambda b:b.__setitem__(slice(0x12,0x14),struct.pack('<H',0xD00C))),
        ('second-rng-draw',lambda b:b.__setitem__(slice(0x40,0x44),struct.pack('<I',0x0206FE9F))),
        ('wrong-stock-location-slot',lambda b:b.__setitem__(slice(0x38,0x3A),struct.pack('<H',0x9201))),
        ('lost-release-token',lambda b:b.__setitem__(slice(0x28,0x2A),struct.pack('<H',0x2101))),
    ):
        b=bytearray(NEW);replacement=mutate(b)
        if isinstance(replacement,bytes):b=replacement
        failed=False
        for case in cases:
            try:check(bytes(b),*case)
            except (AssertionError,KeyError,StopIteration):failed=True;break
        assert failed,('copied native fault passed',name)
        faults[name]='rejected'
    result={'passed':True,'actualThumbCases':len(cases),'baselineBytes':len(OLD),
        'candidateBytes':len(NEW),'maximumInstructions':max(b['instructions'] for _,b in results),
        'baselineLockPairs':sum(a['acquired'] for a,_ in results),
        'candidateLockPairs':sum(b['acquired'] for _,b in results),'sixMemberBatch':batch,
        'faultControls':faults,'candidateImageSha256':hashlib.sha256(NEW).hexdigest(),
        'stockImageSha256':hashlib.sha256(ARM9).hexdigest(),
        'scope':'actual compiled wrapper and unchanged stock Thumb body; deterministic external data/item/RNG/lock leaves; no game timing claim'}
    return result


class WalkingFriendshipTests(unittest.TestCase):
    def packaged_friendship(self):
        rom=ROOT/'test.nds'
        self.assertTrue(rom.is_file(),'native walking test requires current test.nds; build the existing ROM first')
        field_metadata=package_gate.current_field_overlay_metadata()
        base,arm9,overlays=package_gate.packaged_components_from_bytes(rom.read_bytes(),field_metadata)
        self.assertEqual(base,0x02000000)
        package_gate.walking_friendship_native_contracts(arm9)
        start=BASE-field_metadata[0]
        wrapper=overlays[131].data[start:start+68]
        self.assertEqual(wrapper,package_gate.WALKING_FRIENDSHIP_IMAGE)
        return arm9,wrapper

    def test_embedded_bss_never_requests_loader_zeroing_after_the_code(self):
        with tempfile.TemporaryDirectory(prefix="friendship-package-") as directory:
            root = Path(directory)
            (root / "build").mkdir()
            image = bytearray(0x4FB2)
            image[0x4F90:] = b"C" * 34
            output = root / "build/output_field.bin"
            sections = [(8, 3, 0x023CCF5C, 0x2C)]
            with patch.object(package_gate, "REPO", root), patch.object(
                    package_gate, "elf_section_layout", return_value=sections):
                output.write_bytes(image)
                self.assertEqual(package_gate.current_field_overlay_metadata()[1:3], (0x4FB2, 0))
                image[0x4F5C] = 1
                output.write_bytes(image)
                with self.assertRaises(SystemExit):
                    package_gate.current_field_overlay_metadata()
                output.write_bytes(bytes(0x4F5C))
                self.assertEqual(package_gate.current_field_overlay_metadata()[1:3], (0x4F5C, 0x2C))

    def test_actual_source_thumb_preserves_stock_results_rng_and_lock_ownership(self):
        global ARM9,OLD,NEW
        ARM9,wrapper=self.packaged_friendship()
        tools={name:shutil.which('arm-none-eabi-'+name) for name in ('as','ld','objcopy')}
        self.assertTrue(all(tools.values()),'native ARM assembler/linker/objcopy are required')
        source=(ROOT/'src/field/walking_friendship.c').read_text()
        with tempfile.TemporaryDirectory(prefix='walking-native-') as directory:
            folder=Path(directory)
            (folder/'leaf.ld').write_text('SECTIONS { .walking_friendship 0x023CCF90 : { *(.walking_friendship) } ASSERT(SIZEOF(.walking_friendship) <= 72,"fixed field tail") /DISCARD/ : { *(.text) *(.data) *(.bss) } }')
            def assemble(name,assembly):
                src=folder/(name+'.s');obj=folder/(name+'.o');elf=folder/(name+'.elf');out=folder/(name+'.bin')
                src.write_text(assembly)
                for args in ([tools['as'],'-mthumb','-mcpu=arm7tdmi',str(src),'-o',str(obj)],
                    [tools['ld'],'-T',str(folder/'leaf.ld'),str(obj),'-o',str(elf)],
                    [tools['objcopy'],'-O','binary','-j','.walking_friendship',str(elf),str(out)]):
                    completed=subprocess.run(args,capture_output=True,text=True)
                    self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
                return out.read_bytes()
            OLD=assemble('old',BASELINE_ASSEMBLY)
            NEW=assemble('current',native_assembly(source))
        self.assertEqual(NEW,wrapper,'packaged walking adapter differs from current assembled source')
        self.assertEqual(len(OLD),34)
        self.assertEqual(hashlib.sha256(OLD).hexdigest(),'77650226432a7c0562dbb25ab3a39d4b682b35019c3cfdaf9794743d3035384a')
        result=native_results()
        self.assertTrue(result['passed'])
        self.assertEqual(result['actualThumbCases'],338)
        self.assertEqual(len(result['faultControls']),5)

    def test_native_item_predicate_matches_all_authored_items_and_rejects_aliases(self):
        global ARM9
        raw,wrapper=self.packaged_friendship()
        authored=item_gate.authored_item_records()
        item_gate.friendship_item_rule(authored)
        self.assertEqual(len(authored),2558)
        for name in ('build/narc/itemdata.narc','base/root/a/0/1/7'):
            self.assertEqual(item_gate.narc_records((ROOT/name).read_bytes()),authored)
        for item,effect in ((193,53),(474,53),(218,0)):
            changed=list(authored);record=bytearray(changed[item]);record[2]=effect
            changed[item]=bytes(record)
            with self.subTest(item=item,effect=effect),self.assertRaises(ValueError):
                item_gate.friendship_item_rule(changed)

        # Execute the actual current ARM9 body against the exact old five
        # halfwords. Other ARM9 edits do not change this friendship contract.
        original=bytearray(raw)
        for offset,value in ((0x6FED0,0xF007),(0x6FED2,0xFF5A),
            (0x6FED4,0x0600),(0x6FED8,0x0E07),(0x6FF40,0x2F35)):
            struct.pack_into('<H',original,offset,value)
        self.assertEqual(hashlib.sha256(original[0x6FE90:0x6FF88]).hexdigest(),
            'cc827433fc203477b575f46108d9d37ca8a48df77f282f0dc88c855b99342d6a')
        effects=[record[2] for record in authored]

        class ActualItems(Machine):
            def external(self,target):
                if target!=0x02077D88:return super().external(target)
                r=self.r
                assert r[1:3]==[1,0] and r[0]<len(effects)
                self.calls.append(('item',r[0],r[1],r[2]));r[0]=effects[r[0]]
                r[1:4]=[0xDEAD0001,0xDEAD0002,0xDEAD0003];r[12]=0xDEAD000C
                self.pc=r[14]&~1
                return True

        def execute(image,case):
            global ARM9
            ARM9=image
            return ActualItems(wrapper,*case).run()

        def compare(image,case):
            old=execute(original,case);new=execute(image,case)
            assert all(old[key]==new[key] for key in ('mon','seed','locked'))
            assert [call for call in old['calls'] if call[0]!='item']==new['calls']
            assert not any(call[0]=='item' for call in new['calls'])

        cases=[({174:56,6:item,9:70,180:4,152:127},5,127,0,False)
            for item in range(len(authored))]
        cases.extend(({174:56,6:item,9:friendship,180:11,152:127},kind,9,
                0x12345678 if locked else 0,locked)
            for item in (0,193,218,474,730)
            for friendship in (0,99,100,199,200,254,255)
            for kind in (0,4,5,13) for locked in (False,True))
        previous=ARM9
        try:
            for case in cases:compare(raw,case)
            self.assertEqual(len(cases),2838)
            for name,offset,value in (('u8-truncation-restored',0x6FED4,0x0600),
                ('wrong-soothe-id',0x6FF40,0x2FD9),('old-effect-test',0x6FF40,0x2F35)):
                changed=bytearray(raw);struct.pack_into('<H',changed,offset,value)
                if name=='u8-truncation-restored':struct.pack_into('<H',changed,0x6FED8,0x0E07)
                with self.subTest(fault=name),self.assertRaises(AssertionError):
                    for item in (218,474):
                        compare(changed,({174:56,6:item,9:70,180:4,152:127},5,127,0,False))
        finally:
            ARM9=previous

    def test_stock_continuation_contract_rejects_prologue_rng_body_and_return_drift(self):
        raw,_=self.packaged_friendship()
        for offset in (0x6FE90,0x6FE9E,0x6FEA8,0x6FF7C):
            changed=bytearray(raw);changed[offset]^=1
            with self.subTest(offset=offset),self.assertRaises(SystemExit):
                package_gate.walking_friendship_native_contracts(bytes(changed))


if __name__=='__main__':unittest.main()
