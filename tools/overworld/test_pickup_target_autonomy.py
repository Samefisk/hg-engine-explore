"""Production-C action gates distinguish pursuit from actual HELD control."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from tools.overworld.test_picked_up_actor_control import extract_function

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c"

PRELUDE = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef int BOOL;typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;
#define TRUE 1
#define FALSE 0
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_FOLLOWER_SLOT 7
#define OW_WILD_ACTOR_CONTROL_HELD 1
#define OW_WILD_SPAWNER_MOVEMENT_SLOT_MASK(slot) (1u<<(slot))
#define OW_WILD_SPAWNER_SPOT_STATE_EMOTING 1
#define OW_WILD_SPAWNER_SPOT_STATE_TIRED 3
#define OVERWORLD_COMBAT_FAINTED 2
#define OVERWORLD_MOTION_PHASE_COMMIT_PENDING 3
#define OW_WILD_AMBIENT_CRY_MAX_COOLDOWN_TICK 5
typedef struct LocalMapObject {u8 activeMovement;} LocalMapObject;
typedef struct OverworldWildSpawn {LocalMapObject *object;u8 active;u16 species;u8 form;u16 encounterGeneration;} OverworldWildSpawn;
typedef struct FieldSystem {int value;} FieldSystem;
typedef struct Runtime {struct {u16 targetMask,carrierMask;} throwState;} Runtime;
typedef struct OverworldWildSpawnState {
 Runtime *movementRuntimeState;FieldSystem *movementFieldSystem;
 OverworldWildSpawn spawns[10];u8 movementActorControlModes[10];u16 captureTargetMask;
 u8 movementStagedHopPending[10],movementCrashShakeTimers[10],movementSpotStates[10];
 u16 movementInProgressMask;int movementQueuedBattleSlot,pendingSlot;
 u16 pendingMapGeneration,mapGeneration,pendingEncounterGeneration;
 u8 ambientCryCooldown,movementBattleSettleFrames;
} OverworldWildSpawnState;
#define OW_WILD_RUNTIME(state) ((state)->movementRuntimeState)
#define OW_WILD_SPAWNER_BATTLE_SETTLE_FRAMES 2
static int cries,resets,primed,scripts;static BOOL playerBusy,ballBusy,current=TRUE,teleporting;
static int combatResult;
static int Prepare(OverworldWildSpawnState *s,u8 i,void *p){(void)s;(void)i;(void)p;return combatResult;}
static struct {int (*prepare)(OverworldWildSpawnState*,u8,void*);} combat={Prepare};
#define OVERWORLD_COMBAT_ENTRY (&combat)
static BOOL MapObject_IsSingleMovementActive(LocalMapObject *o){return o->activeMovement;}
static BOOL OverworldWildSpawns_IsMovementSlotInProgress(OverworldWildSpawnState *s,int i){return !!(s->movementInProgressMask&(1u<<i));}
static BOOL OverworldWildSpawns_HasConditionalTeleportPresentation(OverworldWildSpawnState *s,int i){(void)s;(void)i;return teleporting;}
static BOOL OverworldWildSpawns_HasPendingBattle(OverworldWildSpawnState *s){return s->pendingSlot>=0;}
static BOOL OverworldWildSpawns_IsPlayerBallProjectileActive(void){return ballBusy;}
static BOOL OverworldWildSpawns_IsPlayerStableForBattle(FieldSystem *f){(void)f;return !playerBusy;}
static BOOL OverworldWildSpawns_PlayerRecoveryPending(FieldSystem *f){(void)f;return FALSE;}
static BOOL OverworldWildSpawns_IsCurrentSpawnObject(FieldSystem *f,OverworldWildSpawn *p){(void)f;(void)p;return current;}
static BOOL OverworldWildSpawns_IsMovementFieldContextCurrent(OverworldWildSpawnState *s,FieldSystem *f){return s->movementFieldSystem==f;}
static void OverworldWildSpawns_PrepareSlotForBattle(OverworldWildSpawnState *s,int i){(void)s;(void)i;}
static void OverworldWildSpawns_ResetAllMovementCommands(OverworldWildSpawnState *s,BOOL a,BOOL b){(void)s;(void)a;(void)b;++resets;}
static void OverworldWildSpawns_PrimePendingBattleForSlot(OverworldWildSpawnState *s,int i){s->pendingSlot=i;++primed;}
static BOOL OverworldWildSpawns_RequestBattleScript(FieldSystem *f,OverworldWildSpawnState *s,int i){(void)f;(void)s;(void)i;++scripts;return TRUE;}
static void OverworldWildSpawns_ResetPendingBattle(OverworldWildSpawnState *s){s->pendingSlot=-1;}
static unsigned gf_rand(void){return 0;}
static void PlayCry(u16 species,u8 form){assert(species==173&&form==0);++cries;}
static void OverworldWildSpawns_ResetAmbientCryCooldown(OverworldWildSpawnState *s){s->ambientCryCooldown=10;}
'''

DRIVER = r'''
static Runtime runtime;static OverworldWildSpawnState state;static FieldSystem field;
static LocalMapObject target;
static void Reset(void){
 memset(&state,0,sizeof(state));memset(&runtime,0,sizeof(runtime));memset(&target,0,sizeof(target));
 state.movementRuntimeState=&runtime;state.movementFieldSystem=&field;
 state.pendingSlot=state.movementQueuedBattleSlot=-1;
 state.spawns[1]=(OverworldWildSpawn){.object=&target,.active=TRUE,.species=173};
 runtime.throwState.targetMask=2;cries=resets=primed=scripts=0;
 playerBusy=ballBusy=teleporting=FALSE;current=TRUE;combatResult=0;
}
int main(void){
 Reset();assert(OverworldWildSpawns_GetHeldThrowTargetMask(&state)==0);
 OverworldWildSpawns_TryPlayAmbientCry(&state);assert(cries==1);
 assert(OverworldWildSpawns_IsSlotStableForBattle(&state,1));
 assert((ContactAux(&state,1,0)&4)==0);
 assert(OverworldWildSpawns_TryStartBattleForSlot(&state,&field,1));
 assert(resets==1&&primed==1&&scripts==1);
 Reset();assert(OverworldWildSpawns_QueueBattleForSlot(&state,&field,1));
 assert(state.movementQueuedBattleSlot==1);
 Reset();assert(OverworldWildSpawns_TryPrimeBattleFromTalkSlot(&state,&field,1));
 assert(resets==1&&primed==1);
 for(int own=0;own<2;++own){
  Reset();state.movementActorControlModes[own?1:2]=OW_WILD_ACTOR_CONTROL_HELD;
  assert(OverworldWildSpawns_GetHeldThrowTargetMask(&state)==(1u<<(own?1:2)));
  assert(!OverworldWildSpawns_TryStartBattleForSlot(&state,&field,1));
  assert(!OverworldWildSpawns_QueueBattleForSlot(&state,&field,1));
  assert(!OverworldWildSpawns_TryPrimeBattleFromTalkSlot(&state,&field,1));
  assert(!resets&&!primed&&!scripts);
  if(own){OverworldWildSpawns_TryPlayAmbientCry(&state);assert(!cries);
   assert(!OverworldWildSpawns_IsSlotStableForBattle(&state,1));
   assert(ContactAux(&state,1,0)&4);}
 }
 for(int gate=0;gate<7;++gate){
  Reset();switch(gate){case 0:runtime.throwState.carrierMask=2;break;
   case 1:state.captureTargetMask=2;break;case 2:state.movementInProgressMask=2;break;
   case 3:target.activeMovement=1;break;case 4:state.movementStagedHopPending[1]=1;break;
   case 5:combatResult=OVERWORLD_COMBAT_FAINTED;break;case 6:teleporting=TRUE;break;}
  assert(!OverworldWildSpawns_IsSlotStableForBattle(&state,1));
 }
 return 0;
}
'''


class PickupTargetAutonomyTests(unittest.TestCase):
    def test_actual_action_gates_keep_claimed_target_free_until_held(self):
        source = SOURCE.read_text()
        bodies = "\n".join(extract_function(source, name, result) for name, result in (
            ("OverworldWildSpawns_GetHeldThrowTargetMask", "u16"),
            ("OverworldWildSpawns_TryPlayAmbientCry", "void"),
            ("OverworldWildSpawns_IsSlotStableForBattle", "BOOL"),
            ("OverworldWildSpawns_TryStartBattleForSlot", "BOOL"),
            ("OverworldWildSpawns_QueueBattleForSlot", "BOOL"),
            ("OverworldWildSpawns_TryPrimeBattleFromTalkSlot", "BOOL")))
        # Execute the exact production contact-call argument, with the native
        # current-object check as the seam. Claims cannot mark ordinary motion
        # as held flight and suppress its own attack launch.
        matches = re.findall(
            r"slot, PLAYER_HEALTH_MOTION_STEP\), &sample,\s*(.*?)\);", source, re.S)
        self.assertEqual(len(matches), 1)
        aux = "static u32 ContactAux(OverworldWildSpawnState *state,int slot,u8 motionPhase){" \
            "Runtime *runtime=OW_WILD_RUNTIME(state);return " + matches[0] + ";}\n"
        with tempfile.TemporaryDirectory(prefix="pickup-target-autonomy-") as directory:
            unit, binary = Path(directory) / "test.c", Path(directory) / "test"
            unit.write_text(PRELUDE + bodies + aux + DRIVER)
            result = subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                "-Wno-unused-function", str(unit), "-o", str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
