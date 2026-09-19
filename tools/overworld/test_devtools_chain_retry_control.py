"""Native callback controls with fake memory; never live retry proof."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import shutil
import struct
import subprocess
import unittest
from unittest.mock import patch
from tools.overworld.devtools_chain_retry_control import NativeChainRetryControl, ChainRetryControlError
from tools.overworld.devtools_observer import NativeObservation


class Registers:
    def __init__(self):
        for i in range(16): setattr(self, "r"+str(i), i)
    sp = property(lambda s:s.r13, lambda s,v:setattr(s,"r13",v))
    lr = property(lambda s:s.r14, lambda s,v:setattr(s,"r14",v))


class Hooks:
    def __init__(self): self.items = {}; self.count = 0
    def add(self, address, callback):
        self.count += 1; self.items[self.count] = (address & ~1,callback); return self.count
    def remove(self, token): self.items.pop(token)


def fixture():
    regs = Registers(); regs.sp = 0x02210000; regs.lr = 0x02300105
    subject = dict(handle=dict(value=65536,slot=0,generation=1,fieldEpoch=2,mapGeneration=2,encounterGeneration=1),
        subjectIdentity=100,species=165,role="WILD",authorityGeneration=1,engineAnchorGeneration=1,presentationGeneration=1,
        engineIdentity=dict(pointer=0x02220000,current_manager=0x02230000,object_manager=0x02230000,manager_index=1))
    actor = deepcopy(subject)
    source = dict(object=0x02220000)
    policy = dict(action=0x85,ticks=8,chain=0)
    memory = SimpleNamespace(register_arm9=regs)
    hooks = Hooks()
    rt = SimpleNamespace(WILD_STATE=0x02240000,EXECUTED_FRAME_COUNT=100,
        movement_policy_state=lambda *_:deepcopy(policy), unsigned=lambda *_:1)
    s = SimpleNamespace(rt=rt,completed_frames=10,native_bridge_active=False,emu=SimpleNamespace(memory=memory),prepared=True)
    entry = 0x02300200
    displacement = entry - (regs.lr & ~1)
    code = struct.pack("<HH",0xf000 | ((displacement >> 12)&0x7ff),0xf800|((displacement>>1)&0x7ff))
    s.read = lambda address,size: code if size == 4 else bytes(32)
    o = SimpleNamespace(session=s,hooks=hooks,tokens=[],return_tokens=[],contexts=[],calls={},MAX_DEPTH=32,
        _chain_current=lambda slot:(deepcopy(actor),deepcopy(source),deepcopy(actor["engineIdentity"]),dict(fieldPointer=0x02250000)),
        _chain_caller=lambda name:None,_chain_words=lambda count:[0,1,2,3,0x02260000,1,0],
        _clock=lambda:dict(actorFrame=10,nativeCycle=100),_queue=lambda *args:None)
    s.native_observation = o
    c = NativeChainRetryControl(s,subject,120)
    s.chain_retry_control = c
    regs.r0=rt.WILD_STATE;regs.r1=0;regs.r2=0x02260000
    parent = c.parent_before()
    regs.r1=0x02250000;regs.r2=0;regs.r3=source["object"]
    value = dict(parent=dict(slot=0,attemptId=1),record=dict(landingIndex=0))
    context = dict(sp=regs.sp,entry=o._clock())
    branches=[]
    memory.set_next_instruction = lambda address:branches.append(address)
    return s,o,c,regs,actor,policy,parent,value,context,entry,branches


class ChainRetryControlTests(unittest.TestCase):
    def test_redirect_once_preserves_registers_and_records_parent(self):
        s,o,c,r,a,p,parent,value,context,entry,branches=fixture()
        before={i:getattr(r,"r"+str(i)) for i in range(15)}
        c.start(value,context,entry)
        self.assertEqual(r.r0,8);self.assertEqual(branches,[r.lr])
        self.assertTrue(all(getattr(r,"r"+str(i))==before[i] for i in range(1,15)))
        c.start(value,context,entry);self.assertEqual(len(branches),1)
        row=c.parent_after(parent,dict(entry=o._clock(),returned=o._clock()))
        self.assertEqual(row["controlAttemptId"],1)
        self.assertEqual(row["attemptIds"],[1]);self.assertEqual(row["movementCooldownAfter"],1)
        c.completed_boundary();c.completed_boundary()
        self.assertEqual(len(c.result()["cooldownBoundaries"]),1)
        c.close();c.close();self.assertTrue(c.result()["closed"])

    def test_real_tap_installs_return_before_branch(self):
        s,o,c,r,a,p,parent,value,context,entry,branches=fixture()
        s.code_regions=[(entry,bytes(32))]
        o.spawn_cost_probe=None
        o.TIMED_CALLS=NativeObservation.TIMED_CALLS
        returned=[]
        def branch(address):
            self.assertTrue(any(pc==(r.lr & ~1) for pc,_ in o.hooks.items.values()))
            branches.append(address)
        s.emu.memory.set_next_instruction=branch
        NativeObservation._tap(o,"chain-prepared-start",entry,bytes(32),lambda:value,
            lambda data,ctx:returned.append(ctx["returnValue"]))
        next(callback for pc,callback in o.hooks.items.values() if pc==entry)()
        next(callback for pc,callback in list(o.hooks.items.values()) if pc==(r.lr&~1))()
        self.assertEqual(returned,[8]);self.assertEqual(len(branches),1)
        self.assertEqual(o.return_tokens,[])

    def test_wrong_owner_action_caller_and_budget_fail_without_redirect(self):
        for fault in ("owner","action","caller","budget"):
            with self.subTest(fault=fault):
                s,o,c,r,a,p,parent,value,context,entry,branches=fixture()
                if fault=="owner":a["authorityGeneration"]+=1
                elif fault=="action":parent["before"]["policy"]["chainPauseAction"]=0x84
                elif fault=="caller":entry+=4
                else:s.completed_frames+=121
                with self.assertRaises(ChainRetryControlError):c.start(value,context,entry)
                self.assertEqual(branches,[]);self.assertIsNotNone(c.failure)

    def test_unrelated_actor_and_closed_scope_do_not_inject(self):
        s,o,c,r,a,p,parent,value,context,entry,branches=fixture()
        value["parent"]["slot"]=1;c.start(value,context,entry)
        self.assertEqual(branches,[])

    def test_unrelated_same_actor_start_is_untouched_but_missing_selected_parent_fails(self):
        s,o,c,r,a,p,parent,value,context,entry,branches=fixture()
        c.parent=None
        p["action"]=0x84
        before={i:getattr(r,"r"+str(i)) for i in range(16)}
        c.start(value,context,entry)
        self.assertEqual(branches,[])
        self.assertEqual(before,{i:getattr(r,"r"+str(i)) for i in range(16)})
        self.assertIsNone(c.failure)
        p["action"]=0x85
        with self.assertRaises(ChainRetryControlError):c.start(value,context,entry)
        c.parent=None;c.close();value["parent"]["slot"]=0;c.start(value,context,entry)
        self.assertEqual(branches,[])

    def test_cooldown_offset_from_actual_arm_header(self):
        compiler=shutil.which("clang")
        self.assertIsNotNone(compiler,"clang needed for real ARM header ABI")
        root=Path(__file__).resolve().parents[2]
        source='''#include "overworld_wild_spawns_internal.h"
#include "overworld_actor_system_internal.h"
_Static_assert(__builtin_offsetof(OverworldWildSpawnState,movementCooldowns)==0xed,"cooldown ABI");
_Static_assert(__builtin_offsetof(OverworldActorPolicyState,chainStepsRemaining)==16,"steps ABI");
_Static_assert(__builtin_offsetof(OverworldActorPolicyState,deferredChainPauseTicks)==17,"ticks ABI");
_Static_assert(__builtin_offsetof(OverworldActorPolicyState,deferredChainPauseAction)==18,"action ABI");
_Static_assert(sizeof(OverworldActorPolicyState)==32,"policy stride");
_Static_assert(OVERWORLD_MOTION_DECISION_PROFILE==8,"retry reason");
_Static_assert(OW_WILD_BEHAVIOR_CHAIN_PAUSE_ACTION_REPOSITION_SKIDS==5,"selected action");
'''
        result=subprocess.run([compiler,"-target","armv5te-none-eabi","-fsyntax-only","-Wno-unknown-attributes",
            "-Wno-gnu-folding-constant","-x","c","-I",str(root/"include"),"-"],input=source,text=True,capture_output=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr[-2000:])

    def test_runtime_arm_mode_and_cleanup_without_advancing(self):
        from tools.overworld.devtools_runtime import DevtoolsSession
        s,o,c,r,a,p,parent,value,context,entry,branches=fixture()
        s.prepared=False;s.chain_retry_control=None
        s.snapshot=lambda **kwargs:dict(prepared=s.prepared)
        operations=[]
        fake=SimpleNamespace(current=lambda:operations.append("current"),install=lambda:operations.append("install"),
            close=lambda:operations.append("close"),result=lambda:dict(injected=False))
        with patch("tools.overworld.devtools_records.select_current_actor",return_value=c.subject), \
             patch("tools.overworld.devtools_chain_retry_control.NativeChainRetryControl",return_value=fake):
            result=DevtoolsSession.chain_retry_arm(s,dict(subject=c.subject,maxFrames=120))
            self.assertEqual(operations,["current","install"])
            self.assertTrue(result["prepared"]);self.assertTrue(result["snapshot"]["prepared"])
            with self.assertRaises(Exception): DevtoolsSession.chain_retry_arm(s,dict(subject=c.subject,maxFrames=120))
            DevtoolsSession.chain_retry_close(s)
        self.assertEqual(operations,["current","install","close"])
        self.assertEqual(branches,[])
