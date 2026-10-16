
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define SPECIES_NONE 0
#define OW_WILD_FOLLOWER_SLOT 7
#define OW_WILD_SPAWNER_PERF_DIAGNOSTICS 0
#define OW_WILD_PERF_INC(x) ((void)0)
#define OW_WILD_BEHAVIOR_LOCOMOTION_HOP_FROM_OFF_SCREEN 2
#define OW_WILD_BEHAVIOR_LOCOMOTION_FLY_IN 3
#define OW_WILD_BEHAVIOR_LOCOMOTION_MOVE_FROM_OFF_SCREEN 4
#define OVERWORLD_ENTRY_ROUTE_ADOPT 1
#define OVERWORLD_PICKUP_ROUTE_REACHABLE 1
#define SEQ_SE_PL_KIRAKIRA 0
typedef int OverworldWildSpawnTerrain;
typedef struct LocalMapObject {int xCurr,yCurr;} LocalMapObject;
typedef struct PlayerAvatar {LocalMapObject*mapObject;} PlayerAvatar;
typedef struct FieldSystem {PlayerAvatar*playerAvatar;} FieldSystem;
typedef struct OverworldWildRolledEncounter {u16 species;u8 level,form;u32 personality;} OverworldWildRolledEncounter;
typedef struct OverworldWildBehaviorProfile {u8 key;} OverworldWildBehaviorProfile;
typedef struct {u8 key;} Primitives;
typedef struct OverworldWildPreparedSpawn {
 OverworldWildRolledEncounter encounter;struct {int startX,startY;}position;
 struct {u8 locomotion;int startX,startY;} startup;
 struct {OverworldWildBehaviorProfile profile;Primitives primitives;int behaviorClass,behaviorLimitKey;}behaviorResolution;
 u8 shiny,playerBallCatchValue;int savedShinySlot;
} OverworldWildPreparedSpawn;
typedef struct {u32 serial;}OverworldEntryRouteReceipt;
typedef struct {int spawnPresentations;u32 entryRouteSerial[10];u8 refillPositionChecksRemaining;}OverworldWildOverlayRuntimeState;
typedef struct OverworldWildSpawnState {OverworldWildOverlayRuntimeState*movementRuntimeState;FieldSystem*movementFieldSystem;u8 shinySpawned;} OverworldWildSpawnState;
#define OW_WILD_RUNTIME(s) ((s)->movementRuntimeState)
static unsigned prepares,creates,initializes,heights,starts,adopts,occupancies;static BOOL occupied;
static LocalMapObject created;
static int OverworldWildSpawns_Abs(int n){return n<0?-n:n;}
static BOOL OverworldWildSpawns_IsTileOccupiedByObject(FieldSystem*f,int x,int y){(void)f;assert(x==30 && y==40);occupancies++;return occupied;}
static int OverworldWildSpawnIdentity_PrepareSlot(FieldSystem*f,OverworldWildSpawnState*s,int n,int*p){(void)f;(void)s;(void)n;(void)p;prepares++;return 0;}
static u32 OverworldWildSpawns_GetSpriteIDForSlot(u16 species,u8 form,u32 personality,int slot){(void)species;(void)form;(void)personality;(void)slot;return 10;}
static LocalMapObject*OverworldWildSpawns_CreateObject(FieldSystem*f,int x,int y,u32 sprite,u8 shiny,const Primitives*p){(void)f;(void)sprite;(void)shiny;(void)p;creates++;created=(LocalMapObject){x,y};return &created;}
static void OverworldWildSpawns_ApplySpawnObjectSetup(int slot,LocalMapObject*object,const OverworldWildRolledEncounter*e,u32 sprite,u8 shiny,const OverworldWildBehaviorProfile*p){(void)slot;(void)object;(void)e;(void)sprite;(void)shiny;(void)p;}
static void OverworldWildSpawns_InitSpawnSlotState(OverworldWildSpawnState*s,FieldSystem*f,int terrain,int slot,LocalMapObject*object,const OverworldWildRolledEncounter*e,u8 shiny,int behavior,int limit,u8 ball){(void)s;(void)f;(void)terrain;(void)slot;(void)object;(void)e;(void)shiny;(void)behavior;(void)limit;(void)ball;initializes++;}
static void OverworldWildSpawns_ResolveObjectLandingHeight(FieldSystem*f,LocalMapObject*object,int x,int y){(void)f;(void)object;(void)x;(void)y;heights++;}
static BOOL OverworldWildSpawns_StartSpawnStartup(OverworldWildSpawnState*s,FieldSystem*f,int slot,const OverworldWildPreparedSpawn*p){(void)s;(void)f;(void)slot;(void)p;starts++;return TRUE;}
static void OverworldWildSpawns_ResetSlotState(OverworldWildSpawnState*s,int n,BOOL del){(void)s;(void)n;(void)del;assert(0);}
static void DeleteMapObject(LocalMapObject*object){(void)object;assert(0);}
static int OverworldWildSpawns_QueryEntry(OverworldWildSpawnState*s,FieldSystem*f,int n,const OverworldWildBehaviorProfile*p,u8 op,const OverworldWildPreparedSpawn*prepared,u8 accepted,u8 idle,u32 sequence,OverworldEntryRouteReceipt*r){(void)s;(void)f;(void)n;(void)p;(void)prepared;assert(op==1 && !accepted && !idle && !sequence);adopts++;r->serial=7;return 1;}
static void OverworldWildSpawns_ClearSavedShiny(OverworldWildSpawnState*s,int n){(void)s;(void)n;assert(0);}
static void PlaySE(int n){(void)n;assert(0);}

#define OVERWORLD_ENTRY_NATIVE_READY 5
typedef struct {BOOL(*occupied)(FieldSystem*,int,int);} OverworldEntryRouteNativeOps;
typedef struct {const OverworldEntryRouteNativeOps*ops;FieldSystem*field;OverworldWildPreparedSpawn*prepared;u8 operation;} OverworldEntryRouteNativeControl;
static int Abs(int n){return n<0?-n:n;}
/* ACTUAL READY OWNER */
static u32 OverworldWildSpawns_EntryControl(OverworldWildSpawnState*s,FieldSystem*f,int slot,const OverworldWildBehaviorProfile*p,OverworldEntryRouteNativeControl*c){(void)s;(void)slot;(void)p;static const OverworldEntryRouteNativeOps ops={OverworldWildSpawns_IsTileOccupiedByObject};assert(c->operation==OVERWORLD_ENTRY_NATIVE_READY);c->ops=&ops;c->field=f;return NativeReady(c);}

/* ACTUAL PREPARED CONSTRUCTOR */

int main(void){
 LocalMapObject player={17,40};PlayerAvatar avatar={&player};FieldSystem field={&avatar};
 OverworldWildOverlayRuntimeState runtime={0};OverworldWildSpawnState state={&runtime};
 OverworldWildPreparedSpawn prepared={0};prepared.encounter.species=161;prepared.encounter.level=5;
 prepared.position.startX=30;prepared.position.startY=40;prepared.startup.locomotion=4;prepared.savedShinySlot=-1;
 runtime.refillPositionChecksRemaining=0xFC; /* Authentic route READY, prior proof origin exactly13 away. */
 player.xCurr=18; /* One stock step after READY puts this same origin inside. */
 assert(!OverworldWildSpawns_SpawnPreparedEncounter(&state,&field,0,0,&prepared));
 assert(!prepares && !creates && !starts && !adopts && !occupancies);
 player.xCurr=17;occupied=TRUE;
 assert(!OverworldWildSpawns_SpawnPreparedEncounter(&state,&field,0,0,&prepared));
 assert(!prepares && !creates && !starts && !adopts && occupancies==1);
 occupied=FALSE;field.playerAvatar=NULL;
 assert(!OverworldWildSpawns_SpawnPreparedEncounter(&state,&field,0,0,&prepared));
 assert(!prepares && !creates && occupancies==1);field.playerAvatar=&avatar;
 assert(OverworldWildSpawns_SpawnPreparedEncounter(&state,&field,0,0,&prepared));
 assert(prepares==1 && creates==1 && initializes==1 && heights==1 && starts==1 && adopts==1 && runtime.entryRouteSerial[0]==7);
 /* The unchanged Y boundary and ordinary visible-spawn behavior are retained. */
 player.xCurr=30;player.yCurr=29;
 assert(OverworldWildSpawns_SpawnPreparedEncounter(&state,&field,0,0,&prepared));
 assert(prepares==2 && creates==2 && adopts==2);
 player.yCurr=40;prepared.startup.locomotion=0;
 assert(OverworldWildSpawns_SpawnPreparedEncounter(&state,&field,0,0,&prepared));
 assert(prepares==3 && creates==3 && adopts==2 && occupancies==3);
 puts("actual READY constructor: moved Player rejects before PrepareSlot; occupied/null origin rejects;13/11 boundary admits; normal spawn unchanged PASS");return 0;
}
