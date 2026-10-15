"""Compile the shared HP/cooldown view without a renderer or extra clocks."""

from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
HARNESS = r'''
#include <assert.h>
#include <string.h>
#include "overworld_appearance_policy.h"

static void CheckDamagePulse(void) {
    const struct { u16 hp; u8 peak; u16 period; } cases[] = {
        {99,2,128},{80,2,128},{79,3,128},{60,3,128},{59,4,64},
        {40,4,64},{39,5,64},{20,5,64},{19,6,32},{0,6,32}
    };
    for (u8 i=0;i<sizeof(cases)/sizeof(cases[0]);i++) {
        u16 hp=cases[i].hp, period=cases[i].period;
        u8 peak=cases[i].peak, maxSeen=0;
        for (u32 frame=0;frame<period;frame++) {
            u8 strength=OverworldAppearancePolicy_DamageStrength(hp,100,frame);
            assert(strength<=peak && strength<=6);
            assert(strength==OverworldAppearancePolicy_DamageStrength(hp,100,
                                                                      frame+period));
            assert(strength==OverworldAppearancePolicy_DamageStrength(hp,100,
                                                                      period-frame));
            if(strength>maxSeen) maxSeen=strength;
        }
        assert(maxSeen==peak);
        assert(OverworldAppearancePolicy_DamageStrength(hp,100,0)==0);
        assert(OverworldAppearancePolicy_DamageStrength(hp,100,1)==0);
        assert(OverworldAppearancePolicy_DamageStrength(hp,100,period-1)==0);
        assert(OverworldAppearancePolicy_DamageStrength(hp,100,period/2)==peak);
        for(u32 frame=0;frame<=period/4;frame++)
            assert(OverworldAppearancePolicy_DamageStrength(hp,100,frame)==0);
        for(u32 frame=period*3/4;frame<period;frame++)
            assert(OverworldAppearancePolicy_DamageStrength(hp,100,frame)==0);
    }
    for (u32 frame=0;frame<256;frame++) {
        assert(OverworldAppearancePolicy_DamageStrength(100,100,frame)==0);
        assert(OverworldAppearancePolicy_DamageStrength(101,100,frame)==0);
        assert(OverworldAppearancePolicy_DamageStrength(1,0,frame)==0);
        assert(OverworldAppearancePolicy_DamageStrength(0,0,frame)==0);
    }
    /* Each more severe group reaches its exact peak sooner. */
    assert(OverworldAppearancePolicy_DamageStrength(75,100,64)==3);
    assert(OverworldAppearancePolicy_DamageStrength(50,100,32)==4);
    assert(OverworldAppearancePolicy_DamageStrength(25,100,32)==5);
    assert(OverworldAppearancePolicy_DamageStrength(0,1,0)==0);
    assert(OverworldAppearancePolicy_DamageStrength(0,1,16)==6);
    assert(OverworldAppearancePolicy_DamageStrength(0,65535,16)==6);
    assert(OverworldAppearancePolicy_DamageStrength(65534,65535,0)==0);
    assert(OverworldAppearancePolicy_DamageStrength(65534,65535,64)==2);
    assert(OverworldAppearancePolicy_DamageStrength(65535,65535,32)==0);
    assert(OverworldAppearancePolicy_DamageStrength(50,100,0xffffffffu)==
           OverworldAppearancePolicy_DamageStrength(50,100,63));
    assert(OverworldAppearancePolicy_DamageStrength(50,100,0xffffffc0u)==
           OverworldAppearancePolicy_DamageStrength(50,100,0));
}

static void PrepareRestCatalog(OverworldWildBehaviorDataBlob *blob,
                               OverworldBehaviorConditionPreparedActor *prepared) {
    /* The two local mask bits refer to global profiles above bit31. */
    prepared->subjectSpecies=173;
    blob->header.overrideProfileCount=36;
    OverworldApplicationBankDirectoryEntry *bank=
        &blob->applicationBankDirectory[OWBD_APPLICATION_BANK_DIRECTORY_COUNT-1];
    bank->first=0; bank->count=2;
    for(int i=0;i<2;i++) {
        blob->applicationBankIndexes[i]=34+i;
        blob->conditionGlobalApplications[i]=34+i;
        blob->applicationRestTint[34+i]=1;
    }
}

static void CheckRestApplicability(void) {
    OverworldWildBehaviorDataBlob blob={0};
    OverworldBehaviorConditionPreparedActor prepared={0};
    OverworldBehaviorConditionEntryState states[2]={0}, before[2];
    PrepareRestCatalog(&blob,&prepared);
    prepared.valid=1; prepared.states=states; prepared.count=2;
    prepared.stateCapacity=2; prepared.catalogEntryIndexes[1]=1;
    blob.header.conditionEntryCount=2;
    for(int i=0;i<2;i++) {
        blob.conditionEntries[i].applicationIndex=i;
        blob.conditionEntries[i].cooldownFrames=20;
    }
    states[0].flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_HAS_TRIGGERED;
    states[0].cooldownUntil=120;
    /* An unrelated Follower-only condition has never triggered. */
    blob.conditionOptions[1].subjectRoleMask=2;
    memcpy(before,states,sizeof(states));
    assert(OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,100,
               OVERWORLD_ACTOR_ROLE_WILD));
    assert(!OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,100,
               OVERWORLD_ACTOR_ROLE_FOLLOWER));
    assert(OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,100,
               OVERWORLD_ACTOR_ROLE_MOUNTED));
    assert(memcmp(before,states,sizeof(states))==0);
    /* An enabled wrong-role condition cannot create blue tint itself. */
    blob.conditionOptions[0].subjectRoleMask=2;
    assert(!OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,100,
               OVERWORLD_ACTOR_ROLE_WILD));
    blob.conditionOptions[0].subjectRoleMask=0;
    /* Bind-only conditions do not contribute a profile, even when active. */
    blob.conditionOptions[1].subjectRoleMask=0;
    blob.conditionOptions[1].captureBinding=1;
    blob.conditionOptions[1].bindOnly=1;
    states[1].flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE;
    memcpy(before,states,sizeof(states));
    assert(OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,100,
               OVERWORLD_ACTOR_ROLE_WILD));
    assert(memcmp(before,states,sizeof(states))==0);
    blob.conditionOptions[0].captureBinding=1;
    blob.conditionOptions[0].bindOnly=1;
    assert(!OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,3,100,
               OVERWORLD_ACTOR_ROLE_WILD));
    blob.conditionOptions[0].bindOnly=0;
    blob.conditionOptions[0].captureBinding=0;
    /* A profile contributor with a missing/stale required binding stays a
     * veto: the evaluator clears its state. usesBinding is not a skip rule. */
    blob.conditionOptions[1].bindOnly=0;
    blob.conditionOptions[1].captureBinding=0;
    blob.conditionOptions[1].usesBinding=1;
    states[1].flags=0;
    assert(!OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,100,
               OVERWORLD_ACTOR_ROLE_WILD));
    states[1].flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_HAS_TRIGGERED;
    states[1].cooldownUntil=100;
    assert(!OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,100,
               OVERWORLD_ACTOR_ROLE_WILD));
    states[1].cooldownUntil=120;
    assert(OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,100,
               OVERWORLD_ACTOR_ROLE_WILD));
    assert(!OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,100,0));
    assert(!OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,100,4));
    assert(!OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,100,255));
}

int main(void) {
    OverworldWildBehaviorDataBlob blob = {0};
    OverworldBehaviorConditionPreparedActor prepared = {0};
    OverworldBehaviorConditionEntryState states[2] = {0}, before[2];
    PrepareRestCatalog(&blob,&prepared);
    CheckDamagePulse();
    CheckRestApplicability();
    prepared.valid=1; prepared.states=states; prepared.stateCapacity=2;
    blob.header.conditionEntryCount=2;
    assert(!OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,100,OVERWORLD_ACTOR_ROLE_WILD));
    prepared.count=2; prepared.catalogEntryIndexes[1]=1;
    for(int i=0;i<2;i++) {
        blob.conditionEntries[i].applicationIndex=i;
        blob.conditionEntries[i].cooldownFrames=20;
        states[i].flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_HAS_TRIGGERED;
        states[i].cooldownUntil=120;
    }
    memcpy(before,states,sizeof(states));
    assert(OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,100,OVERWORLD_ACTOR_ROLE_WILD));
    assert(memcmp(before,states,sizeof(states))==0);
    assert(!OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,0,100,OVERWORLD_ACTOR_ROLE_WILD));
    assert(!OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,120,OVERWORLD_ACTOR_ROLE_WILD));
    states[1].cooldownUntil=100;
    assert(!OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,100,OVERWORLD_ACTOR_ROLE_WILD));
    states[1].cooldownUntil=120;
    states[1].flags|=OVERWORLD_BEHAVIOR_CONDITION_STATE_ACTIVE;
    assert(!OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,100,OVERWORLD_ACTOR_ROLE_WILD));
    states[1].flags=0;
    assert(!OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,100,OVERWORLD_ACTOR_ROLE_WILD));
    states[1].flags=OVERWORLD_BEHAVIOR_CONDITION_STATE_HAS_TRIGGERED;
    blob.conditionEntries[1].cooldownFrames=0;
    assert(!OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,100,OVERWORLD_ACTOR_ROLE_WILD));
    blob.conditionEntries[1].cooldownFrames=20;
    states[0].cooldownUntil=states[1].cooldownUntil=0;
    assert(OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,0xfffffff0,OVERWORLD_ACTOR_ROLE_WILD));
    assert(!OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,0,OVERWORLD_ACTOR_ROLE_WILD));
    prepared.catalogEntryIndexes[1]=2;
    assert(!OverworldAppearancePolicy_ShouldRestTint(&prepared,&blob,1,0xfffffff0,OVERWORLD_ACTOR_ROLE_WILD));
    return 0;
}
'''


class AppearancePolicyTests(unittest.TestCase):
    def compile_and_run(self, policy_text=None):
        with tempfile.TemporaryDirectory(prefix="appearance-policy-") as directory:
            source = Path(directory) / "check.c"
            binary = Path(directory) / "check"
            source.write_text(HARNESS)
            policy = ROOT / "lib/overworld/overworld_appearance_policy.c"
            if policy_text is not None:
                policy = Path(directory) / "policy.c"
                policy.write_text(policy_text)
            compiled = subprocess.run(shlex.split(os.environ.get("CC", "cc")) + [
                "-std=c99", "-O2", "-DOVERWORLD_BEHAVIOR_HOST",
                "-DOVERWORLD_ACTOR_SYSTEM_HOST", "-I", str(ROOT / "include"),
                "-I", str(ROOT / "lib/overworld"), str(source), str(policy),
                "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            return subprocess.run([str(binary)], capture_output=True, text=True)

    def test_production_hp_and_existing_cooldown_view(self):
        ran = self.compile_and_run()
        self.assertEqual(ran.returncode, 0, ran.stdout + ran.stderr)

    def test_applicability_skip_guards_are_required(self):
        policy = (ROOT / "lib/overworld/overworld_appearance_policy.c").read_text()
        mutations = {
            "wrong-role": policy.replace("mask & roleMask", "roleMask", 1),
            "bind-only": policy.replace("options->bindOnly ? 0 : mask & roleMask", "mask & roleMask", 1),
        }
        for name, changed in mutations.items():
            with self.subTest(name=name):
                self.assertNotEqual(changed, policy)
                ran = self.compile_and_run(changed)
                self.assertNotEqual(ran.returncode, 0, ran.stdout + ran.stderr)


if __name__ == "__main__":
    unittest.main()
