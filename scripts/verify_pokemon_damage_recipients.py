#!/usr/bin/env python3
"""Check actual shared contact helpers and packed recipient/knockback controls."""
from pathlib import Path
import subprocess
import re
import tempfile

ROOT=Path(__file__).resolve().parents[1]
STUBS=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int32_t s32;typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define PLAYER_HEALTH_CLIP_ATTRIBUTE
#define PLAYER_HEALTH_HOST
#define OW_WILD_MAX_SPAWNS 10
#define COMBAT_CODE
#define PLAYER_HEALTH_OK 0
#define OW_WILD_FOLLOWER_SLOT 7
#define SEQ_SE_DP_WALL_HIT2 1
typedef struct LocalMapObject { s32 posVec[3],faceVec[3],unk88[3]; } LocalMapObject;
typedef struct Avatar { LocalMapObject *mapObject; } Avatar;
typedef struct FieldSystem { Avatar *playerAvatar; } FieldSystem;
typedef struct Spawn { LocalMapObject *object;u16 encounterGeneration; } Spawn;
typedef struct OverworldWildSpawnState { FieldSystem *movementFieldSystem;Spawn spawns[10]; } OverworldWildSpawnState;
static unsigned publishes,lastPublished;
static void CombatContact_PublishPlayerDamage(const OverworldWildSpawnState *w,u8 s){publishes++;lastPublished=s;}
typedef struct OverworldMotionSample { s32 renderX,renderY,renderZ; } OverworldMotionSample;
static int mounted,playerContacts,pokemonHits,knockbacks;static u16 sourceHp=20;
static unsigned playerHp,pokemonHp[10];
static BOOL CombatContact_Current(const OverworldWildSpawnState *w,u8 s){return s!=9&&w->spawns[s].object!=NULL;}
static BOOL PlayerHealthField_ContactsEnabled(FieldSystem *f){return 1;}
static BOOL PlayerHealth_ContactCanDamage(u8 a,u8 min,u8 dmg,u16 speed){return a&&dmg&&speed>=min;}
static BOOL OverworldCombat_ReadHp(const OverworldWildSpawnState *w,u8 s,u16 *hp,u16 *max){*hp=sourceHp;*max=20;return 1;}
static BOOL CombatContact_IsMounted(FieldSystem *f){return mounted;}
static BOOL PlayerHealthField_TryContact(FieldSystem *f,u8 a,u8 min,u8 dmg,u16 speed,u8 options,u8 direction){playerContacts++;playerHp-=dmg;return 1;}
static BOOL acceptedHit=TRUE;
static BOOL OverworldCombat_TryHit(const OverworldWildSpawnState *w,u8 target,u8 dmg,u8 options,u8 direction){pokemonHits++;if(!acceptedHit)return FALSE;pokemonHp[target]-=dmg;return TRUE;}
static void PlayerHealthField_QueueKnockback(FieldSystem *f,u8 options,u8 direction){knockbacks++;}
static void PlaySE(int sound){}
'''
CASES=r'''
int main(void){
 LocalMapObject dummy={0};Avatar avatar={&dummy};FieldSystem field={&avatar};
 OverworldWildSpawnState wild={&field};
 for(u8 slot=0;slot<10;slot++){wild.spawns[slot].object=&dummy;wild.spawns[slot].encounterGeneration=1;}
 for(u8 recipients=0;recipients<8;recipients++){
  u8 options=OW_WILD_BEHAVIOR_COLLISION_OPTIONS(2,3,recipients);
  assert(OW_WILD_BEHAVIOR_KNOCKBACK_TYPE(options)==2);
  assert(OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE(options)==3);
  OW_WILD_BEHAVIOR_SET_KNOCKBACK_DISTANCE(options,7);
  OW_WILD_BEHAVIOR_SET_KNOCKBACK_TYPE(options,1);
  assert(OW_WILD_BEHAVIOR_DAMAGE_RECIPIENTS(options)==recipients);
  assert(OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE(options)==7);
  for(u8 role=1;role<=4;role*=2){
   int allowed=recipients==0||(recipients&role);
   mounted=0;playerContacts=pokemonHits=knockbacks=0;
   if(role==1) CombatContact_HitPlayer(&wild,0,1,16,20,32,options,1);
   else CombatContact_HitPokemon(&wild,0,role==4?7:1,1,16,20,32,options,1);
   assert((role==1?playerContacts:pokemonHits)==!!allowed);
  }
 }
 /* Shared follower flight protects Player and Allied on incidental mounted contact. */
 u8 follower=OW_WILD_BEHAVIOR_COLLISION_OPTIONS(1,1,OW_WILD_BEHAVIOR_DAMAGE_RECIPIENT_WILD);
 mounted=1;playerContacts=pokemonHits=knockbacks=0;
 CombatContact_HitPlayer(&wild,0,1,16,20,32,follower,1);
 CombatContact_HitPokemon(&wild,0,7,1,16,20,32,follower,1);
 assert(playerContacts==0&&pokemonHits==0&&knockbacks==0);
 CombatContact_HitPokemon(&wild,0,1,1,16,20,32,follower,1);assert(pokemonHits==1);
 sourceHp=0;CombatContact_HitPokemon(&wild,0,1,1,16,20,32,follower,1);assert(pokemonHits==1);
 /* Only accepted subject HP loss reaches the generic subject event. */
 sourceHp=20;mounted=0;publishes=pokemonHits=0;acceptedHit=FALSE;
 CombatContact_HitPokemon(&wild,0,1,1,16,20,32,follower,1);assert(pokemonHits==1&&!publishes);
 acceptedHit=TRUE;CombatContact_HitPokemon(&wild,0,1,1,16,20,32,follower,1);
 assert(publishes==1&&lastPublished==(1|OVERWORLD_BEHAVIOR_CONDITION_PUBLISH_SUBJECT_DAMAGE));
 acceptedHit=FALSE;CombatContact_HitPokemon(&wild,0,1,1,16,20,32,follower,1);assert(publishes==1);
 CombatContact_HitPokemon(&wild,0,1,1,16,20,15,follower,1);assert(pokemonHits==3&&publishes==1);
 acceptedHit=TRUE;
 /* Actual shared flight dispatcher must keep rider and body HP separate.
  * The actor and player boxes use their real render/face offsets. Native HP
  * writes are seam stubs; clip, sweep and dispatch are production C. */
 sourceHp=20;mounted=1;
 LocalMapObject body={0},rider={0};avatar.mapObject=&rider;
 rider.faceVec[1]=32768;rider.faceVec[2]=32768;
 for(u8 slot=0;slot<10;slot++)wild.spawns[slot].object=NULL;
 wild.spawns[0].object=&dummy;wild.spawns[7].object=&body;
 u8 options=OW_WILD_BEHAVIOR_COLLISION_OPTIONS(1,1,0);
 for(u8 boxes=0;boxes<3;boxes++){
  PlayerHealthThrowTracker tracker={0};OverworldMotionSample motion;
  s32 height=boxes==0?0:boxes==1?98304:32768;
  s32 oldZ=boxes==1?0:-32768,newZ=boxes==0?0:32768;
  tracker.active=1;tracker.attacking=1;tracker.minImpactSpeed=16;
  tracker.collisionDamage=20;tracker.knockbackOptions=options;tracker.ownerSlot=0;
  tracker.projectileY=height;tracker.projectileZ=oldZ;
  tracker.relativeX=0;tracker.relativeY=(height-rider.faceVec[1])>>6;
  tracker.relativeZ=(oldZ-rider.faceVec[2])>>6;
  motion.renderX=0;motion.renderY=height;motion.renderZ=newZ;
  playerContacts=pokemonHits=knockbacks=0;playerHp=100;pokemonHp[7]=50;
  PlayerHealthContact_StepMotion(&tracker,&wild,0,&motion,1);
  assert(playerHp==(boxes==0?100:80));
  assert(pokemonHp[7]==(boxes==1?50:30));
  assert(playerContacts==(boxes!=0)&&pokemonHits==(boxes!=1));
  assert(knockbacks==(boxes!=1));
 }
 puts("shared damage recipients and separate mounted flight hitboxes: pass");return 0;
}
'''
def function(source,name):
 start=source.index(name+'(');start=source.rfind('\n',0,start)+1
 if not source[start:].startswith('static '):start=source.rfind('\n',0,start-1)+1
 body=source.index('{',start);end=body+1;depth=1
 while depth:
  depth+=(source[end]=='{')-(source[end]=='}');end+=1
 return source[start:end]

def main(source_path=None):
 header=(ROOT/'include/overworld_wild_behavior_data.h').read_text()
 macros=header[header.index('#define OW_WILD_BEHAVIOR_KNOCKBACK_NONE'):header.index('#define OW_WILD_BEHAVIOR_CONDITION_SUBJECT_APPLICATION_NONE')]
 macros+='\n'+re.search(r'^#define OVERWORLD_BEHAVIOR_CONDITION_PUBLISH_SUBJECT_DAMAGE .+$',
  (ROOT/'include/overworld_behavior_condition_adapter.h').read_text(),re.M).group(0)+'\n'
 source=(source_path or ROOT/'src/player_health_contact.c').read_text().replace('__attribute__((noinline, section(".player_health_tail")))','__attribute__((noinline))')
 helpers=source[source.index('static void COMBAT_CODE CombatContact_HitPokemon'):source.index('void PlayerHealthContact_ResetAll')]
 geometry=(ROOT/'lib/overworld/overworld_contact_geometry.c').read_text()
 geometry_header=(ROOT/'include/overworld_contact_geometry.h').read_text()
 types=re.search(r'typedef struct PlayerHealthContactSegment \{.*?\} PlayerHealthContactSegment;',geometry_header,re.S).group(0)+'\n'
 types+=source[source.index('typedef struct PlayerHealthThrowTracker'):source.index('static PlayerHealthThrowTracker sThrow')]
 types+=source[source.index('typedef struct CombatContactPose'):source.index('static CombatContactPose sContactPose')]
 types+='static PlayerHealthThrowTracker sThrow[10];static CombatContactPose sContactPose[10];\n'
 movement='\n'.join(function(geometry,name) for name in (
  'PlayerHealthContact_ClipAxis','OverworldContactGeometry_Intersects'))
 # The native host branch uses this same alias; keep the sole pure hit-box body.
 movement+='\n#define PlayerHealthContact_ThrowIntersectsPlayer OverworldContactGeometry_Intersects\n'
 movement+='\n'.join(function(source,name) for name in (
  'PlayerHealthContact_AwayDirection','CombatContact_Sweep',
  'PlayerHealthContact_StepMotion'))
 with tempfile.TemporaryDirectory(prefix='hg-recipients-') as folder:
  file=Path(folder)/'contact.c';binary=Path(folder)/'contact';file.write_text(STUBS+macros+types+helpers+movement+CASES)
  subprocess.run(['cc','-std=c99','-O2',str(file),'-o',str(binary)],check=True)
  subprocess.run([str(binary)],check=True)

DAMAGE_SOURCE_STUBS=r"""
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define OVERWORLD_BEHAVIOR_HOST
#define OVERWORLD_ACTOR_SYSTEM_HOST
#define OverworldActorSystem_IsReady Header_OverworldActorSystem_IsReady
#include "overworld_behavior_condition_runtime.h"
#include "overworld_target_bindings.h"
#undef OverworldActorSystem_IsReady
/* ACTUAL_ADAPTER_RUNTIME_TYPES */
#define BOOL int
#define TRUE 1
#define FALSE 0
#define COMBAT_CODE
#include "player_health_model.h"
#define PLAYER_HEALTH_TAIL_SECTION
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_FOLLOWER_SLOT 7
#define MAPOBJECTFLAG_ACTIVE 1
#define OVERWORLD_ACTOR_FIELD_CONTEXT_MAP_GENERATION(value) (value)
typedef struct LocalMapObject { u32 flags; int id; } LocalMapObject;
typedef struct MapObjectMan { LocalMapObject *objects;u32 object_count; } MapObjectMan;
typedef struct Location { u16 mapId; } Location;
typedef struct SaveData {u8 hp;} SaveData;
struct FieldSystem { Location *location;void *mapObjectMan;SaveData *savedata; };
struct OverworldWildSpawn { LocalMapObject *object;u32 personality;u16 species,mapId,encounterGeneration;u8 active,objectId; };
typedef OverworldWildSpawn Spawn;
struct OverworldWildSpawnState { FieldSystem *movementFieldSystem;void *movementRuntimeState;u16 mapGeneration;Spawn spawns[10]; };
typedef struct OverworldWildOverlayRuntimeState { OverworldWildBehaviorConditionRuntime *conditions; } OverworldWildOverlayRuntimeState;
typedef struct OverworldActorSystemState { u32 frame;u16 fieldEpoch;struct {OverworldActorStateSnapshot snapshot;} slots[10]; } OverworldActorSystemState;
static OverworldActorSystemState nativeSystem;
#define OVERWORLD_ACTOR_SYSTEM_STATE_ADDR (&nativeSystem)
static FieldSystem *gFieldSysPtr;static LocalMapObject *objects[10];
static int ready=1,combatReady=1,hpAvailable=1,hpValue=20,contactResult,contacts;
static BOOL OverworldActorSystem_IsReady(void){return ready;}
static void *GetMapObjectByID(void *manager,u8 id){return objects[id];}
static u32 context(void){return nativeSystem.slots[0].snapshot.handle.mapGeneration;}
static struct { u32 (*getContext)(void); } compat={context};
#define OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY (&compat)
typedef u16 OverworldBehaviorConditionHandleHalfword __attribute__((may_alias));
static BOOL OverworldCombat_ReadHp(const OverworldWildSpawnState *w,u8 s,u16 *hp,u16 *maximum){*hp=hpValue;*maximum=20;return hpAvailable;}
static struct {u8 initialized;SaveData *saveData;FieldSystem *fieldSystem;PlayerHealthState health;} sPlayerHealth;
static BOOL PlayerHealthField_IsEligible(FieldSystem *f){return f==gFieldSysPtr;}
static BOOL PlayerHealthField_IsMounted(FieldSystem *f){return 0;}
static void PlayerHealthSave_SetHP(SaveData *s,u8 hp){s->hp=hp;}
static void PlaySE(int value){}
#define SEQ_SE_DP_WALL_HIT2 1
static OverworldWildSpawnState sOverworldWildSpawnState;
static void OverworldCombat_AcceptedHit(const OverworldWildSpawnState *w,u8 slot){}
static void PlayerHealthField_QueueKnockback(FieldSystem *f,u8 options,u8 direction){}
static PlayerHealthDecision PlayerHealthField_RealTryContact(FieldSystem *,u8,u8,u8,u16,u8,u8);
static int PlayerHealthField_TryContact(FieldSystem *f,u8 a,u8 m,u8 d,u16 v,u8 o,u8 direction){contacts++;return contactResult>=0?contactResult:PlayerHealthField_RealTryContact(f,a,m,d,v,o,direction);}
static BOOL OverworldCombat_IsReady(void){return combatReady;}
static struct {BOOL (*readHp)(const OverworldWildSpawnState *,u8,u16 *,u16 *);} combat={OverworldCombat_ReadHp};
#define OVERWORLD_COMBAT_ENTRY (&combat)
"""
DAMAGE_SOURCE_CASES=r"""
static OverworldWildBehaviorConditionRuntime conditions;
static OverworldWildOverlayRuntimeState runtime={&conditions};
static LocalMapObject nativeObjects[10];static MapObjectMan mapManager={nativeObjects,10};
static Location location={33};static SaveData saveData;static FieldSystem field={&location,&mapManager,&saveData};
static OverworldWildSpawnState wild;
static void init(void){
 memset(&conditions,0,sizeof(conditions));memset(&nativeSystem,0,sizeof(nativeSystem));memset(&wild,0,sizeof(wild));
 ready=combatReady=hpAvailable=1;hpValue=20;contacts=contactResult=0;
 wild.movementFieldSystem=gFieldSysPtr=&field;wild.movementRuntimeState=&runtime;wild.mapGeneration=4;
 nativeSystem.frame=100;nativeSystem.fieldEpoch=3;
 memset(&sPlayerHealth,0,sizeof(sPlayerHealth));sPlayerHealth.initialized=1;sPlayerHealth.fieldSystem=&field;sPlayerHealth.saveData=&saveData;sPlayerHealth.health.frameActive=1;sPlayerHealth.health.hp=100;
 for(u8 s=0;s<10;s++){
  nativeObjects[s].flags=1;nativeObjects[s].id=s;objects[s]=&nativeObjects[s];
  wild.spawns[s]=(Spawn){&nativeObjects[s],1000+s,74,33,20+s,1,s};
  OverworldActorHandle h={s,10+s,3,4,20+s,0};
  nativeSystem.slots[s].snapshot.handle=h;nativeSystem.slots[s].snapshot.active=1;
  nativeSystem.slots[s].snapshot.subjectIdentity=1000+s;nativeSystem.slots[s].snapshot.species=74;
  conditions.actors[s].subject=h;conditions.actors[s].valid=1;
  conditions.frame.world.actors[s].actor=h;conditions.frame.world.actors[s].valid=1;
 }
 conditions.frame.world.actorCount=10;conditions.frame.valid=1;
}
static void hit(u8 source){CombatContact_HitPlayer(&wild,source,1,0,20,32,0,0);}
static int marked(u8 source){return !!(conditions.frame.world.actors[source].facingAndOcclusion&OVERWORLD_BEHAVIOR_CONDITION_OBSERVATION_PLAYER_DAMAGE_SOURCE);}
static void publish(void){hit(1);assert(conditions.playerDamage.pendingMask==1023);assert(conditions.playerDamage.source.slot==1);assert(conditions.playerDamage.frame==100);assert(!conditions.frame.valid);}
int main(void){
 /* Real stock-facing acceptance rejects mere contact, slow impact, paused
  * frames, protected HP and recovery; only a true HP write publishes. */
 init();contactResult=-1;CombatContact_HitPlayer(&wild,1,0,0,20,32,0,0);assert(!conditions.playerDamage.pendingMask&&sPlayerHealth.health.hp==100);
 init();contactResult=-1;CombatContact_HitPlayer(&wild,1,1,33,20,32,0,0);assert(!conditions.playerDamage.pendingMask);
 init();contactResult=-1;CombatContact_HitPlayer(&wild,1,1,0,0,32,0,0);assert(!conditions.playerDamage.pendingMask);
 init();contactResult=-1;sPlayerHealth.health.frameActive=0;hit(1);assert(!conditions.playerDamage.pendingMask);
 init();contactResult=-1;sPlayerHealth.health.protectionFrames=1;hit(1);assert(!conditions.playerDamage.pendingMask);
 init();contactResult=-1;sPlayerHealth.health.recoveryPending=1;hit(1);assert(!conditions.playerDamage.pendingMask);
 init();contactResult=-1;hit(1);assert(conditions.playerDamage.pendingMask==1023&&sPlayerHealth.health.hp==80&&saveData.hp==80);hit(2);assert(conditions.playerDamage.source.slot==1&&sPlayerHealth.health.hp==80);
 init();for(int decision=1;decision<=6;decision++){contactResult=decision;hit(1);assert(!conditions.playerDamage.pendingMask);}assert(contacts==6);
 init();CombatContact_PublishPlayerDamage(&wild,10);CombatContact_PublishPlayerDamage(&wild,255);assert(!conditions.playerDamage.pendingMask);
 init();hpValue=0;hit(1);assert(!contacts&&!conditions.playerDamage.pendingMask);
 init();hpAvailable=0;hit(1);assert(!contacts&&!conditions.playerDamage.pendingMask);
 init();CombatContact_HitPlayer(&wild,1,1,0,20,32,OW_WILD_BEHAVIOR_COLLISION_OPTIONS(0,0,OW_WILD_BEHAVIOR_DAMAGE_RECIPIENT_WILD),0);assert(!contacts&&!conditions.playerDamage.pendingMask);
 init();nativeSystem.slots[1].snapshot.handle.generation++;hit(1);assert(!conditions.playerDamage.pendingMask);
 init();nativeObjects[1].id=99;hit(1);assert(!conditions.playerDamage.pendingMask);
 init();publish();OverworldBehaviorConditionAdapter_PlayerDamage(&conditions,&wild,&field,7);assert(marked(1));
 /* Pending survives an accepted move: publication/observation cannot consume. */
 nativeSystem.frame=355;OverworldBehaviorConditionAdapter_PlayerDamage(&conditions,&wild,&field,7);assert(marked(1)&&conditions.playerDamage.pendingMask==1023);
 OverworldWildBehaviorConditionEntry entry={0};entry.kind=OVERWORLD_BEHAVIOR_CONDITION_PLAYER_DAMAGED;entry.conditionId=41;
 OverworldTargetBinding *binding=&conditions.bindings[7].bindings[OVERWORLD_TARGET_BINDING_OBJECT_OF_INTEREST];
 binding->flags=OVERWORLD_TARGET_BINDING_BOUND;binding->target.kind=OVERWORLD_BEHAVIOR_TARGET_REFERENCE_ACTOR;binding->target.actor=conditions.playerDamage.source;binding->sourceConditionId=41;
 OverworldBehaviorConditionAdapter_ConsumePlayerDamage(&conditions,7,&entry,0);assert(conditions.playerDamage.pendingMask==1023);
 binding->target.actor.generation++;OverworldBehaviorConditionAdapter_ConsumePlayerDamage(&conditions,7,&entry,4);assert(conditions.playerDamage.pendingMask==1023);binding->target.actor.generation--;
 entry.kind=OVERWORLD_BEHAVIOR_CONDITION_POKEMON_NOTICED;OverworldBehaviorConditionAdapter_ConsumePlayerDamage(&conditions,7,&entry,4);assert(conditions.playerDamage.pendingMask==1023);entry.kind=OVERWORLD_BEHAVIOR_CONDITION_PLAYER_DAMAGED;
 OverworldBehaviorConditionAdapter_ConsumePlayerDamage(&conditions,7,&entry,4);assert(!(conditions.playerDamage.pendingMask&(1u<<7)));
 OverworldBehaviorConditionAdapter_PlayerDamage(&conditions,&wild,&field,7);assert(!marked(1));
 /* Another subject in the cached frame still gets exactly its own mark. */
 OverworldBehaviorConditionAdapter_PlayerDamage(&conditions,&wild,&field,8);assert(marked(1));
 conditions.actors[8].subject.generation++;OverworldBehaviorConditionAdapter_PlayerDamage(&conditions,&wild,&field,8);assert(!marked(1)&&!(conditions.playerDamage.pendingMask&(1u<<8)));
 /* Physical thrown Cargo is the caller source; no carrier/owner substitution. */
 init();hit(3);assert(conditions.playerDamage.source.slot==3);
 init();publish();conditions.frame.world.actors[1].actor.generation++;OverworldBehaviorConditionAdapter_PlayerDamage(&conditions,&wild,&field,7);assert(!marked(1)&&!conditions.playerDamage.pendingMask);
 init();publish();conditions.frame.world.actors[1].valid=0;OverworldBehaviorConditionAdapter_PlayerDamage(&conditions,&wild,&field,7);assert(!conditions.playerDamage.pendingMask);
 init();publish();hpValue=0;OverworldBehaviorConditionAdapter_PlayerDamage(&conditions,&wild,&field,7);assert(!conditions.playerDamage.pendingMask);
 init();publish();hpAvailable=0;OverworldBehaviorConditionAdapter_PlayerDamage(&conditions,&wild,&field,7);assert(!conditions.playerDamage.pendingMask);
 init();publish();combatReady=0;OverworldBehaviorConditionAdapter_PlayerDamage(&conditions,&wild,&field,7);assert(!conditions.playerDamage.pendingMask);
 init();publish();conditions.actors[7].subject.mapGeneration++;OverworldBehaviorConditionAdapter_PlayerDamage(&conditions,&wild,&field,7);assert(!conditions.playerDamage.pendingMask);
 init();publish();FieldSystem other=field;OverworldBehaviorConditionAdapter_PlayerDamage(&conditions,&wild,&other,7);assert(!conditions.playerDamage.pendingMask);
 init();publish();OverworldWildSpawns_ClearAllConditionState(&conditions);assert(!conditions.playerDamage.pendingMask&&conditions.playerDamage.fieldSystem==NULL&&conditions.playerDamage.frame==0);
 puts("accepted player damage physical source, pending/consume/context/faint guards: pass");return 0;
}
"""

def damage_source_definition(source, name):
 for match in re.finditer(r'\b'+re.escape(name)+r'\s*\(',source):
  end=source.index('(',match.start())+1;depth=1
  while depth:
   depth+=(source[end]=='(')-(source[end]==')');end+=1
  body=end
  while source[body].isspace():body+=1
  if source[body]!='{':continue
  start=source.rfind('\n',0,match.start())+1
  if not source[start:].startswith(('static ','void ')):start=source.rfind('\n',0,start-1)+1
  end=body+1;depth=1
  while depth:
   depth+=(source[end]=='{')-(source[end]=='}');end+=1
  return source[start:end]
 raise AssertionError('missing production definition: '+name)

def verify_player_damage_source(contact_path=None, adapter_path=None, wild_path=None, include_path=None):
 contact=(contact_path or ROOT/'src/player_health_contact.c').read_text().replace('__attribute__((noinline, section(".player_health_tail")))','__attribute__((noinline))')
 adapter=(adapter_path or ROOT/'lib/overworld/overworld_player_damage_condition.c').read_text()
 wild=(wild_path or ROOT/'src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c').read_text()
 header=(ROOT/'include/overworld_wild_behavior_data.h').read_text()
 macros=header[header.index('#define OW_WILD_BEHAVIOR_KNOCKBACK_NONE'):header.index('#define OW_WILD_BEHAVIOR_CONDITION_SUBJECT_APPLICATION_NONE')]
 model=(ROOT/'lib/overworld/player_health_model.c').read_text();field_source=(ROOT/'src/player_health.c').read_text()
 parts=[damage_source_definition(model,'PlayerHealth_ContactCanDamage'),damage_source_definition(model,'PlayerHealth_TryHit'),damage_source_definition(field_source,'PlayerHealthField_TryContact').replace('PlayerHealthField_TryContact(','PlayerHealthField_RealTryContact(').replace('PlayerHealthDecision __attribute__((noinline,\n    section(".overworld_combat_text")))','PlayerHealthDecision')]
 parts+=[damage_source_definition(contact,'CombatContact_Current'), damage_source_definition(adapter,'OverworldPlayerDamageCondition_Publish').replace('OverworldPlayerDamageCondition_Publish(', 'CombatContact_PublishPlayerDamage(').replace(', BOOL (*current)(const OverworldWildSpawnState *, u8)', '').replace('!current(wild, source)', '!CombatContact_Current(wild, source)'), damage_source_definition(contact,'CombatContact_HitPlayer')]
 parts+=[damage_source_definition(adapter,name) for name in ('OverworldBehaviorConditionAdapter_HandleEquals','OverworldBehaviorConditionAdapter_PlayerDamage','OverworldBehaviorConditionAdapter_ConsumePlayerDamage')]
 parts+=['static void OverworldWildSpawns_ClearConditionActorRecord(OverworldWildBehaviorConditionRuntime *c,int slot){}',damage_source_definition(wild,'OverworldWildSpawns_ClearAllConditionState')]
 with tempfile.TemporaryDirectory(prefix='hg-player-hit-source-') as folder:
  source=Path(folder)/'source.c';binary=Path(folder)/'source'
  adapter_header=((include_path or ROOT/'include')/'overworld_behavior_condition_adapter.h').read_text()
  actual_types=adapter_header[adapter_header.index('typedef struct FieldSystem FieldSystem;'):adapter_header.index('#if !defined(OVERWORLD_BEHAVIOR_HOST)')]
  source.write_text(DAMAGE_SOURCE_STUBS.replace('/* ACTUAL_ADAPTER_RUNTIME_TYPES */',actual_types)+'\n'.join(parts)+DAMAGE_SOURCE_CASES)
  subprocess.run(['cc','-std=c11','-O2','-Wno-unknown-attributes','-I',str(include_path or ROOT/'include'),'-I',str(ROOT/'include'),str(source),'-o',str(binary)],check=True)
  subprocess.run([str(binary)],check=True)

VERTICAL_CONTACT_STUBS=r'''
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#define PLAYER_HEALTH_HOST
#include "player_health_model.h"
typedef int16_t s16;
typedef int BOOL;
#define __attribute__(attributes)
#define TRUE 1
#define FALSE 0
#define COMBAT_CODE
#define PLAYER_HEALTH_CLIP_ATTRIBUTE
#define PLAYER_HEALTH_TAIL_SECTION
#define OW_WILD_MAX_SPAWNS 10
#define OW_WILD_FOLLOWER_SLOT 7
#define SEQ_SE_DP_WALL_HIT2 1
#define MON_DATA_HP 1
#define COMBAT_IMMUNITY_FRAMES 60
#define OVERWORLD_COMBAT_PENDING_KNOCKBACK 1
typedef struct LocalMapObject {s32 posVec[3],faceVec[3],unk88[3];} LocalMapObject;
typedef struct Avatar {LocalMapObject *mapObject;} Avatar;
typedef struct Location {u16 mapId;} Location;
typedef struct SaveData {u8 hp;} SaveData;
typedef struct FieldSystem {Avatar *playerAvatar;Location *location;void *savedata;} FieldSystem;
typedef struct Spawn {LocalMapObject *object;u16 encounterGeneration;} Spawn;
typedef struct OverworldWildSpawnState {FieldSystem *movementFieldSystem;Spawn spawns[10];void *movementRuntimeState;u16 mapGeneration;} OverworldWildSpawnState;
typedef struct OverworldMotionSample {s32 renderX,renderY,renderZ;} OverworldMotionSample;
typedef struct OverworldCombatTarget {u16 immunityFrames,currentHp,hitCount;u8 lastDamage,knockbackOptions,knockbackDirection,knockbackPending;} OverworldCombatTarget;
struct PartyPokemon {int unused;};
static struct {const OverworldWildSpawnState *frameState;} sCombat;
static struct {u16 savedHp[10];} gOverworldWildResidentData;
static OverworldCombatTarget targets[10];
static struct {u8 initialized;SaveData *saveData;FieldSystem *fieldSystem;PlayerHealthState health;} sPlayerHealth;
static struct {u8 pending,active,waitFrames,direction,type,distance,mounted;u16 mapId;FieldSystem *fieldSystem;} sKnockback;
static unsigned publishes,lastPublished;static BOOL contactsEnabled=TRUE,sourceAlive=TRUE;
static BOOL CombatContact_Current(const OverworldWildSpawnState *w,u8 s){return s<10&&w->spawns[s].object!=NULL;}
static BOOL PlayerHealthField_ContactsEnabled(FieldSystem *f){return contactsEnabled&&f==sPlayerHealth.fieldSystem;}
static BOOL PlayerHealthField_IsEligible(FieldSystem *f){return f==sPlayerHealth.fieldSystem;}
static BOOL PlayerHealthField_IsMounted(FieldSystem *f){return FALSE;}
static BOOL CombatContact_IsMounted(FieldSystem *f){return FALSE;}
static BOOL Combat_IsMounted(const OverworldWildSpawnState *w,u8 s){return FALSE;}
static BOOL OverworldCombat_ReadHp(const OverworldWildSpawnState *w,u8 s,u16 *hp,u16 *maximum){*hp=sourceAlive?20:0;*maximum=20;return TRUE;}
static void CombatContact_PublishPlayerDamage(const OverworldWildSpawnState *w,u8 s){publishes++;lastPublished=s;}
static void PlayerHealthSave_SetHP(SaveData *s,u8 hp){s->hp=hp;}
static void PlaySE(int sound){}
static void OverworldCombat_AcceptedHit(const OverworldWildSpawnState *w,u8 s){}
static void SetMonData(struct PartyPokemon *p,int field,const u16 *hp){}
static void OverworldFollowerSelector_SetPartySnapshotDirty(void){}
static OverworldCombatTarget *Combat_ReadTarget(const OverworldWildSpawnState *w,u8 s,u16 *hp,u16 *max,struct PartyPokemon **p){*hp=gOverworldWildResidentData.savedHp[s];*max=50;*p=NULL;return &targets[s];}
static OverworldWildSpawnState sOverworldWildSpawnState;
'''

VERTICAL_CONTACT_CASES=r'''
static LocalMapObject body,player;
static Avatar avatar={&player};static Location location={33};static SaveData save;
static FieldSystem field={&avatar,&location,&save};
static PlayerHealthWildRuntimePrefix runtime;
static void ResetFlight(u8 heading){
 memset(&runtime,0,sizeof(runtime));memset(sThrow,0,sizeof(sThrow));memset(sContactPose,0,sizeof(sContactPose));
 memset(&sPlayerHealth,0,sizeof(sPlayerHealth));memset(&sKnockback,0,sizeof(sKnockback));memset(&sOverworldWildSpawnState,0,sizeof(sOverworldWildSpawnState));
 memset(targets,0,sizeof(targets));memset(&player,0,sizeof(player));memset(&body,0,sizeof(body));
 contactsEnabled=sourceAlive=TRUE;publishes=0;
 sPlayerHealth.initialized=1;sPlayerHealth.saveData=&save;sPlayerHealth.fieldSystem=&field;
 sPlayerHealth.health.hp=100;sPlayerHealth.health.frameActive=1;save.hp=100;
 sOverworldWildSpawnState.movementFieldSystem=&field;sOverworldWildSpawnState.movementRuntimeState=&runtime;
 sOverworldWildSpawnState.spawns[0]=(Spawn){&body,1};sOverworldWildSpawnState.spawns[1]=(Spawn){&body,2};
 sCombat.frameState=&sOverworldWildSpawnState;gOverworldWildResidentData.savedHp[1]=50;
 runtime.movementCustomJumpStartX[0]=runtime.movementCustomJumpStartY[0]=10;
 runtime.movementCustomJumpTargetX[0]=10+(heading==2?-2:heading==3?2:0);
 runtime.movementCustomJumpTargetY[0]=10+(heading==0?-2:heading==1?2:0);
 player.posVec[0]=body.posVec[0]=runtime.movementCustomJumpTargetX[0]*65536+32768;
 player.posVec[2]=body.posVec[2]=runtime.movementCustomJumpTargetY[0]*65536+32768;
 PlayerHealthContact_LaunchMotion(&sThrow[0],&sOverworldWildSpawnState,0,1,16,20,
  OW_WILD_BEHAVIOR_COLLISION_OPTIONS(OW_WILD_BEHAVIOR_KNOCKBACK_JUMP,2,0),FALSE);
}
static void AtPeak(void){
 /* The first available contact sample can be the vertical drop. Launch must
  * supply its real displacement heading without needing a horizontal sample. */
 sThrow[0].projectileX=player.posVec[0];sThrow[0].projectileZ=player.posVec[2];sThrow[0].projectileY=131072;
 sThrow[0].relativeX=sThrow[0].relativeZ=0;sThrow[0].relativeY=2048;
}
static void Step(s32 x,s32 y,s32 z,u32 aux){OverworldMotionSample m={x,y,z};PlayerHealthContact_StepMotion(&sThrow[0],&sOverworldWildSpawnState,0,&m,aux);}
static void ExpectAccepted(u8 heading){
 assert(sPlayerHealth.health.hp==80&&save.hp==80&&gOverworldWildResidentData.savedHp[1]==30);
 printf("HP Player%u Pokemon%u; queued Player%u Pokemon%u; heading%u\n",sPlayerHealth.health.hp,gOverworldWildResidentData.savedHp[1],sKnockback.pending,targets[1].knockbackPending,sKnockback.direction);fflush(stdout);
 assert(sKnockback.pending&&sKnockback.direction==heading&&sKnockback.type==OW_WILD_BEHAVIOR_KNOCKBACK_JUMP&&sKnockback.distance==2);
 assert((targets[1].knockbackPending&OVERWORLD_COMBAT_PENDING_KNOCKBACK)&&targets[1].knockbackDirection==heading);
 assert(OW_WILD_BEHAVIOR_KNOCKBACK_TYPE(targets[1].knockbackOptions)==OW_WILD_BEHAVIOR_KNOCKBACK_JUMP&&OW_WILD_BEHAVIOR_KNOCKBACK_DISTANCE(targets[1].knockbackOptions)==2);
}
int main(void){
 for(u8 heading=0;heading<4;heading++){
  ResetFlight(heading);AtPeak();Step(player.posVec[0],0,player.posVec[2],3);ExpectAccepted(heading);
  ResetFlight(heading);Step(player.posVec[0],0,player.posVec[2],1);ExpectAccepted(heading);
  ResetFlight(heading);Step(player.posVec[0],131072,player.posVec[2],1);
  assert(sPlayerHealth.health.hp==100&&gOverworldWildResidentData.savedHp[1]==50);
  Step(player.posVec[0],131072,player.posVec[2],1);Step(player.posVec[0],0,player.posVec[2],3);ExpectAccepted(heading);
 }
 for(unsigned rejected=0;rejected<6;rejected++){
  ResetFlight(1);AtPeak();
  if(rejected==0)sourceAlive=FALSE;
  if(rejected==1){sPlayerHealth.health.protectionFrames=1;targets[1].immunityFrames=1;}
  if(rejected==2)sThrow[0].attacking=0;
  if(rejected==3)sThrow[0].collisionDamage=0;
  if(rejected==4){sPlayerHealth.health.frameActive=0;contactsEnabled=FALSE;}
  if(rejected==5){sThrow[0].projectileY=16384;sThrow[0].relativeY=256;}
  Step(player.posVec[0],rejected==5?16128:0,player.posVec[2],1);
  assert(sPlayerHealth.health.hp==100&&gOverworldWildResidentData.savedHp[1]==50&&!publishes);
  assert(!sKnockback.pending&&!targets[1].knockbackPending);
 }
 ResetFlight(1);AtPeak();sThrow[0].knockbackOptions=OW_WILD_BEHAVIOR_COLLISION_OPTIONS(0,0,0);
 Step(player.posVec[0],0,player.posVec[2],3);assert(sPlayerHealth.health.hp==80&&gOverworldWildResidentData.savedHp[1]==30);
 assert(!sKnockback.pending&&!targets[1].knockbackPending);
 puts("shared vertical/horizontal/hang contact, Jump2, rejected/slow controls: pass");return 0;
}
'''

def verify_vertical_contact_heading(source_path=None, *, expected_pass=True):
 contact=(source_path or ROOT/'src/player_health_contact.c').read_text().replace('__attribute__((noinline, section(".player_health_tail")))','__attribute__((noinline))')
 header=(ROOT/'include/overworld_wild_behavior_data.h').read_text()
 macros=header[header.index('#define OW_WILD_BEHAVIOR_KNOCKBACK_NONE'):header.index('#define OW_WILD_BEHAVIOR_CONDITION_SUBJECT_APPLICATION_NONE')]
 macros+='\n'+re.search(r'^#define OVERWORLD_BEHAVIOR_CONDITION_PUBLISH_SUBJECT_DAMAGE .+$',(ROOT/'include/overworld_behavior_condition_adapter.h').read_text(),re.M).group(0)+'\n'
 prefix=re.search(r'^#define OVERWORLD_WILD_CUSTOM_JUMP_RUNTIME_PREFIX_FIELDS .*?(?=\n\n)',(ROOT/'include/overworld_wild_spawns_internal.h').read_text(),re.M|re.S).group(0)
 types=prefix+'\n'+contact[contact.index('typedef struct PlayerHealthWildRuntimePrefix'):contact.index('static PlayerHealthThrowTracker sThrow')]
 types+=contact[contact.index('typedef struct CombatContactPose'):contact.index('static CombatContactPose sContactPose')]
 types+='static PlayerHealthThrowTracker sThrow[10];static CombatContactPose sContactPose[10];\n'
 geometry=(ROOT/'lib/overworld/overworld_contact_geometry.c').read_text()
 types+=re.search(r'typedef struct PlayerHealthContactSegment \{.*?\} PlayerHealthContactSegment;',(ROOT/'include/overworld_contact_geometry.h').read_text(),re.S).group(0)+'\n'
 parts=[damage_source_definition((ROOT/'lib/overworld/player_health_model.c').read_text(),name) for name in ('PlayerHealth_ContactCanDamage','PlayerHealth_TryHit')]
 parts+=[damage_source_definition((ROOT/'src/player_health.c').read_text(),name) for name in ('PlayerHealthField_QueueKnockback','PlayerHealthField_TryContact')]
 parts+=[damage_source_definition((ROOT/'src/player_health_pokemon.c').read_text(),'OverworldCombat_TryHit')]
 parts+=[damage_source_definition(contact,name) for name in ('CombatContact_HitPokemon','CombatContact_HitPlayer','PlayerHealthContact_AwayDirection')]
 parts+=[damage_source_definition(geometry,name) for name in ('PlayerHealthContact_ClipAxis','OverworldContactGeometry_Intersects')]
 parts+=['#define PlayerHealthContact_ThrowIntersectsPlayer OverworldContactGeometry_Intersects']
 parts+=[damage_source_definition(contact,name) for name in ('CombatContact_Sweep','PlayerHealthContact_StepMotion','PlayerHealthContact_LaunchMotion')]
 with tempfile.TemporaryDirectory(prefix='hg-vertical-contact-') as folder:
  file=Path(folder)/'contact.c';binary=Path(folder)/'contact';file.write_text(VERTICAL_CONTACT_STUBS+macros+types+'\n'.join(parts)+VERTICAL_CONTACT_CASES)
  subprocess.run(['cc','-std=c11','-O2','-I',str(ROOT/'include'),str(file),'-o',str(binary)],check=True)
  result=subprocess.run([str(binary)],text=True,capture_output=True)
  if expected_pass:
   assert result.returncode==0,result.stdout+result.stderr
   print(result.stdout,end='')
  else:
   assert result.returncode!=0 and 'HP Player80 Pokemon30; queued Player0 Pokemon0' in result.stdout,result.stdout+result.stderr
  return result

def verify_vertical_contact_negative_controls():
 source=(ROOT/'src/player_health_contact.c').read_text()
 changes=(
  ('else direction = tracker->impactDirection;','else direction = 4;'),
  ('tracker->impactDirection = PlayerHealthContact_AwayDirection(\n        runtime->movementCustomJumpStartX[slot] - runtime->movementCustomJumpTargetX[slot],\n        runtime->movementCustomJumpStartY[slot] - runtime->movementCustomJumpTargetY[slot]);',
   'tracker->impactDirection = 4;'),
 )
 with tempfile.TemporaryDirectory(prefix='hg-vertical-contact-controls-') as folder:
  for index,(old,new) in enumerate(changes):
   assert source.count(old)==1
   copy=Path(folder)/('control-'+str(index)+'.c');copy.write_text(source.replace(old,new))
   verify_vertical_contact_heading(copy,expected_pass=False)
 print('copied missing vertical fallback and missing launch heading reject: pass')

if __name__=='__main__':
 main()
 verify_player_damage_source()
 verify_vertical_contact_heading()
 verify_vertical_contact_negative_controls()
