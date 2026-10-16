#!/usr/bin/env python3
"""Reject wrong query ELF modes, relocation inventory and native ABI."""
from pathlib import Path
import importlib.util
import struct
import json
import hashlib

ROOT=Path(__file__).resolve().parents[1]
import argparse
parser=argparse.ArgumentParser(description='Exact ARM query package fault controls')
parser.add_argument('--elf',type=Path,required=True)
parser.add_argument('--package',type=Path,required=True)
parser.add_argument('--second-image',type=Path,required=True)
args=parser.parse_args()
HERE=ROOT/'build/tickets/query-code-addon-v2'
spec=importlib.util.spec_from_file_location('addon_packer', ROOT/'tools/overworld/pack_query_code_addon.py')
packer=importlib.util.module_from_spec(spec); spec.loader.exec_module(packer)
raw=args.elf.read_bytes()
blob,receipt=packer.package(raw)
assert blob==args.package.read_bytes()
# Link the same object set independently at a second ordinary heap address.
image=bytearray(blob[64:64+receipt['imageBytes']])
for offset in receipt['localAbs32']:
    word=struct.unpack_from('<I',image,offset)[0]
    struct.pack_into('<I',image,offset,word+0x100000)
assert bytes(image)==args.second_image.read_bytes()

table=struct.unpack_from('<I',raw,32)[0]
stride,count,names_index=struct.unpack_from('<HHH',raw,46)
sections=[struct.unpack_from('<10I',raw,table+i*stride) for i in range(count)]
n=sections[names_index]; names=raw[n[4]:n[4]+n[5]]
def name(strings,offset):return strings[offset:strings.index(b'\0',offset)].decode()
indices={name(names,row[0]):i for i,row in enumerate(sections)}
text_index=indices['.text']
symidx=next(i for i,row in enumerate(sections) if row[1]==2)
symtab=sections[symidx]
strtab=sections[symtab[6]]; strings=raw[strtab[4]:strtab[4]+strtab[5]]
symbols=[struct.unpack_from('<IIIBBH',raw,o) for o in range(symtab[4],symtab[4]+symtab[5],16)]
symnames={name(strings,row[0]):i for i,row in enumerate(symbols)}
relidx=next(i for i,row in enumerate(sections) if row[1]==9 and row[5])
rel=sections[relidx]
relocs=[(o,*struct.unpack_from('<II',raw,o)) for o in range(rel[4],rel[4]+rel[5],8)]
firstcall=next(o for o,a,info in relocs if (info&255)==10)
firstabs=next(o for o,a,info in relocs if (info&255)==2)
controls=[]
def reject(label,mutate):
    bad=bytearray(raw); mutate(bad)
    try:packer.package(bad)
    except ValueError as e:controls.append({'control':label,'reason':str(e)})
    else:raise AssertionError('control was accepted: '+label)

def u32(b,o,v):struct.pack_into('<I',b,o,v)
def symbol_offset(name_):return symtab[4]+16*symnames[name_]
reject('unsupported relocation',lambda b:u32(b,firstabs+4,(struct.unpack_from('<I',b,firstabs+4)[0]&~255)|3))
reject('missing relocation inventory',lambda b:u32(b,table+relidx*40+20,0))
reject('untyped import',lambda b:b.__setitem__(symbol_offset('memcpy')+12,b[symbol_offset('memcpy')+12]&0xF0))
reject('wrong fixed import',lambda b:u32(b,symbol_offset('memcpy')+4,0x023DEE01))
reject('external direct Thumb call',lambda b:u32(b,firstcall+4,(symnames['memcpy']<<8)|10))
for import_name in packer.IMPORTS:
    if import_name.startswith("OverworldCondition"):
        reject(import_name + " untyped", lambda b, n=import_name:
               b.__setitem__(symbol_offset(n)+12, b[symbol_offset(n)+12] & 0xF0))
        reject(import_name + " wrong target", lambda b, n=import_name:
               u32(b, symbol_offset(n)+4, packer.IMPORTS[n] ^ 2))
reject('ARM callback metadata',lambda b:u32(b,symbol_offset(packer.FUNCTIONS[0])+4,symbols[symnames[packer.FUNCTIONS[0]]][1]&~1))
reject('mutable image',lambda b:u32(b,table+text_index*40+8,7))
attrs=indices['.ARM.attributes']
reject('second allocated section',lambda b:u32(b,table+attrs*40+8,2))
text=sections[text_index]
reject('wrong entry layout',lambda b:struct.pack_into('<H',b,text[4]+6,60))
reject('stale package entry version',lambda b:struct.pack_into('<H',b,text[4]+4,3))
reject('stale package entry size',lambda b:struct.pack_into('<H',b,text[4]+6,188))
reject('wrong Cargo prefix boundary',lambda b:u32(b,symbol_offset('__query_cargo_code_end')+4,packer.BASE+packer.ENTRY))
reject('wrong return tail boundary',lambda b:u32(b,symbol_offset('__query_return_code_end')+4,packer.BASE+receipt['imageBytes']-4))
reject('stale Native terrain callback ABI',lambda b:struct.pack_into('<H',b,text[4]+18,2))
reject('stale Condition world layout',lambda b:struct.pack_into('<H',b,text[4]+78,240))
reject('stale Condition runtime ABI',lambda b:struct.pack_into('<H',b,text[4]+76,9))
reject('old private version6',lambda b:struct.pack_into('<H',b,text[4]+4,6))
reject('old private version7',lambda b:struct.pack_into('<H',b,text[4]+4,7))
reject('old Condition runtime12',lambda b:struct.pack_into('<H',b,text[4]+76,12))
for n in ('OverworldBehaviorResolver_QueryCall','OverworldBehaviorPackedOptions_Apply'):
    reject(n+' untyped',lambda b,n=n:b.__setitem__(symbol_offset(n)+12,b[symbol_offset(n)+12]&0xF0))
    reject(n+' even Thumb target',lambda b,n=n:u32(b,symbol_offset(n)+4,symbols[symnames[n]][1]&~1))
reject('wrong resolver callback68',lambda b:u32(b,text[4]+68,struct.unpack_from('<I',b,text[4]+64)[0]))

reject('old prepared actor52',lambda b:struct.pack_into('<H',b,text[4]+80,52))
reject('oversized native image',lambda b:u32(b,table+text_index*40+20,packer.MAX_IMAGE+4))
reject('oversized Cargo prefix',lambda b:u32(b,symbol_offset('__query_cargo_code_end')+4,packer.BASE+packer.CARGO_PREFIX_CAP+4))
reject('stale Cargo storage layout',lambda b:struct.pack_into('<H',b,text[4]+108,18456))
reject('ARM final callback metadata',lambda b:u32(b,symbol_offset(packer.FUNCTIONS[-1])+4,symbols[symnames[packer.FUNCTIONS[-1]]][1]&~1))
report={'scope':'real fully linked ARM image; no ROM/game run or source edits',
    'positive':receipt,'independentSecondBase':0x02180000,'twoBaseBytesMatch':True,
    'rejections':controls,'packerSha256':hashlib.sha256((ROOT/'tools/overworld/pack_query_code_addon.py').read_bytes()).hexdigest()}
(HERE/'package-controls-receipt.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'ARM package controls passed: {len(controls)} rejected variants; independent two-base bytes match')
