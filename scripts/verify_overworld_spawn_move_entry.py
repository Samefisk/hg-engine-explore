#!/usr/bin/env python3
"""Actual-C Move entry host regression builders.

Use the current shared product source by default. Existing Pickup/Cargo host
fixtures replace named stock callbacks and native layouts only. These checks
prove route, ownership and caller ordering; not ARM layout or game pacing.
"""
from pathlib import Path
import re
import os
import shlex
import subprocess
from scripts import verify_overworld_pickup_route_wild as pickup
from scripts import verify_overworld_cargo_query_wild as cargo

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parents[1] / 'tools/overworld/fixtures'
ENTRY_FAULTS = {
    'height-budget': ('Read(w,2,8)', 'Read(w,2,1)'),
    'same-commit': (' || slot->snapshot.commitSequence<=p->acceptedSequence', ''),
    'on-screen': (' && offscreen;', ';'),
    'proof-stall-reset': ('if (!sameTrip) path->noProgress=0;', 'path->noProgress=0;'),
}

def product_path(root, relative):
    candidate = Path(root) / relative
    return candidate if candidate.exists() else ROOT / relative


def product(root, relative):
    return product_path(root, relative).read_text()


def without_includes(source):
    return re.sub(r'^#include [^\n]+\n', '', source, flags=re.M)


def type_decl(source, name, kind='struct'):
    match = re.search(r'typedef ' + kind + ' ' + name + r'\s*\{.*?\}\s*' + name + ';', source, re.S)
    if not match:
        raise AssertionError('production type changed: ' + name)
    return match.group(0)


def mutate(source, old, new):
    if source.count(old) != 1:
        raise AssertionError('copied mutation seam changed: ' + old)
    return source.replace(old, new, 1)


def wild_function(source, name):
    match = re.search(r'\b' + name + r'\s*\([^;{}]*\)\s*\{', source)
    if not match:
        raise AssertionError('production function changed: ' + name)
    start = source.rfind('\nstatic ', 0, match.start()) + 1
    end, depth = match.end(), 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def route_program(root=ROOT, fault=None):
    pro = '#define TRUE 1\n#define FALSE 0\n' + pickup.PROLOG[:pickup.PROLOG.index('static int nativeHeightReady')]
    pro = pro.replace('OverworldActorStateSnapshot snapshot;struct {u16 targetSurfaceId;} policy;',
                      'OverworldActorStateSnapshot snapshot;OverworldMotionState motion;struct {u16 targetSurfaceId;} policy;')
    pro = pro[:pro.index('typedef struct OverworldActorHopPlanCall')]
    pro += 'struct OverworldActorHopClearanceCursor;\n' + type_decl(product(root, 'include/overworld_actor_system_internal.h'), 'OverworldActorHopPlanCall') + '\n'
    pro += '#define OVERWORLD_ACTOR_HOP_PLAN_CLEARANCE_BEGIN 3\n#define OVERWORLD_ACTOR_HOP_PLAN_CLEARANCE_STEP 4\n'
    pro += type_decl(product(root, 'src/pokemon_move_history_task6_overlay/overworld_actor_hop_geometry.h'), 'OverworldActorHopGeometry') + '\n'
    for relative in ('include/overworld_actor_hop_clearance.h', 'include/overworld_prepared_movement.h', 'include/overworld_entry_route.h'):
        pro += without_includes(product(root, relative)).split('/* Native glue')[0] + ('\n#endif\n' if relative.endswith('overworld_entry_route.h') else '') + '\n'
    pro = pro.replace('#define OVERWORLD_ACTOR_HOP_PLAN_FLAG_SPAWN_ENTRY 1',
                      '#include "overworld_cargo_query.h"\n#define OVERWORLD_ACTOR_HOP_PLAN_FLAG_SPAWN_ENTRY 1')
    body = without_includes(product(root, 'lib/overworld/overworld_entry_route.c')).split('/* Synchronous native glue')[0]
    if fault:
        body = mutate(body, *ENTRY_FAULTS[fault])
    return {'check.c': pro + body + (FIXTURES / 'spawn_move_route_driver.c').read_text()}



def ledge_program(root=ROOT, fault=None):
    """Run the real reverse Entry/memo/classifier and shared ledge reducer.

    Only named stock callbacks are mocked. The two copied faults retain the
    old expensive admission or remove the negative-predecessor read guard.
    """
    source = product(root, 'lib/overworld/overworld_entry_route.c')
    if fault == 'old-ledge-path':
        start = source.index('    if (s->reverse && (edge->tag>>OVERWORLD_PICKUP_ROUTE_NATIVE_KIND_SHIFT)==OVERWORLD_PICKUP_ROUTE_NATIVE_LEDGE')
        end = source.index('    if (!s->reverse) return OverworldPickupRouteNative_Classify(', start)
        source = source[:start] + source[end:]
    elif fault == 'negative-predecessor-read':
        source = mutate(source,
            '        && from->x+edge->dx>=0 && from->y+edge->dy>=0\n', '')
    elif fault is not None:
        raise AssertionError('unknown ledge copied fault: ' + fault)
    full = route_program(root)['check.c']
    driver = (FIXTURES / 'spawn_move_route_driver.c').read_text()
    if not full.endswith(driver):
        raise AssertionError('actual Entry route fixture tail changed')
    body = without_includes(product(root, 'lib/overworld/overworld_entry_route.c')).split('/* Synchronous native glue')[0]
    changed = without_includes(source).split('/* Synchronous native glue')[0]
    full = mutate(full[:-len(driver)], body, changed)
    prepared = without_includes(product(root, 'lib/overworld/overworld_prepared_movement.c'))
    prepared = prepared.replace('Abs(', 'PreparedAbs(')
    return {'check.c': full + prepared + (FIXTURES / 'spawn_move_ledge_driver.c').read_text()}


def cargo_fixture(root):
    def typ(relative, name, kind='struct'):
        return type_decl(product(root, relative), name, kind)
    def plain(relative):
        return without_includes(product(root, relative))
    fixture=(ROOT/'tools/overworld/fixtures/cargo_query_wild_harness.c').read_text()
    fixture=fixture.replace('#define OW_WILD_BEHAVIOR_LOCOMOTION_HOP 2','#define OW_WILD_BEHAVIOR_LOCOMOTION_HOP 2\n#define OW_WILD_BEHAVIOR_LOCOMOTION_IS_TELEPORT(v) ((v)==3)\n#define OW_WILD_SPAWN_ENTRY_MOVE 1')
    fixture=fixture.replace('freeBytes=100000','freeBytes=sizeof(NativeQuery)+OVERWORLD_FIELD_PICKUP_QUERY_HEAP_RESERVE+10000')
    fixture=fixture.replace('u8 continueWhenArrived;','u8 continueWhenArrived,jumpLevel;')
    fixture=fixture.replace('const u8 *land;','const u8 *land;void *savedata;')
    fixture=fixture.replace('OverworldActorStateSnapshot snapshot; struct {u16 targetSurfaceId;} policy;','OverworldActorStateSnapshot snapshot; OverworldMotionState motion;struct {u16 targetSurfaceId;} policy;')
    fixture=fixture.replace('u16 fieldEpoch,mapGeneration; } OverworldActorSystemState;','u16 fieldEpoch,mapGeneration;u32 frame; } OverworldActorSystemState;')
    fixture=fixture.replace('typedef struct OverworldActorRuntimeSlot {','#include "overworld_motion_model.h"\ntypedef struct OverworldActorRuntimeSlot {')
    parts=typ('include/overworld_actor_system_internal.h','OverworldActorHopPlanCall')+'\n'
    parts='struct OverworldActorHopClearanceCursor;\n'+parts
    geo=product(root, 'src/pokemon_move_history_task6_overlay/overworld_actor_hop_geometry.h');parts+=re.search(r'typedef struct OverworldActorHopGeometry\s*\{.*?\}\s*OverworldActorHopGeometry;',geo,re.S).group(0)+'\n'
    parts+=plain('include/overworld_actor_hop_clearance.h')+plain('include/overworld_prepared_movement.h')+plain('include/overworld_entry_route.h').split('/* Native glue')[0]+'\n#endif\n'
    fixture=fixture.replace('typedef struct OverworldWildOverlayRuntimeState {','\n#define SPECIES_NONE 0\n#define MAPOBJECTFLAG_UNK2 (1u<<2)\n#define MAPOBJECTFLAG_UNK11 (1u<<11)\n#define MAPOBJECTFLAG_UNK12 (1u<<12)\n#define MAPOBJECTFLAG_SINGLE_MOVEMENT (1u<<1)\n#define OW_WILD_BEHAVIOR_OVERRIDE_PROFILE_FOLLOWER 16\n#define OW_WILD_SPAWN_MOVE_DESTINATION_PENDING 0xFB\n#define OW_WILD_SPAWN_ROUTE_READY 0xFC\n#define OW_WILD_SPAWN_ROUTE_PENDING 0xFD\n#define OW_WILD_SPAWN_STARTUP_PENDING 0xFE\n#define OW_WILD_PROFILE_DESTINATION_SCAN_PENDING 0xFF\n#define OW_WILD_SPOT_STATE_OWNER 0\n#define OW_WILD_RETURN_NONE 0\n#define chillAction hopTime\ntypedef enum OverworldWildHelperPrepareResult {OW_WILD_HELPER_PREPARE_FAILED=0,OW_WILD_HELPER_PREPARE_READY=1,OW_WILD_HELPER_PREPARE_POSITION_PENDING=2} OverworldWildHelperPrepareResult;\ntypedef struct OverworldWildQueuedSpawnGuard {u32 owner[16];} OverworldWildQueuedSpawnGuard;\ntypedef int OverworldWildSpawnTerrain;\ntypedef struct OverworldWildSpawnPosition {int startX,startY;u8 headbuttTreeType;} OverworldWildSpawnPosition;\ntypedef struct OverworldWildSpawnStartup {s16 targetX,targetY,startX,startY;u8 locomotion,hopDirection;s32 targetBaseY;} OverworldWildSpawnStartup;\ntypedef struct OverworldWildBehaviorPrimitives {u8 spawnLocomotion;u8 other[7];} OverworldWildBehaviorPrimitives;\n'+parts+'''\ntypedef struct OverworldWildPreparedSpawn {
        union {u8 nativeUnobserved[260];struct {
        OverworldWildSpawnPosition position;struct {u32 personality;u16 species;u8 form,level;} encounter;
        OverworldWildSpawnStartup startup;struct {OverworldWildBehaviorProfile profile;OverworldWildBehaviorPrimitives primitives;u8 behaviorLimitKey;} behaviorResolution;
        int savedShinySlot;u8 shiny; }; };
    } OverworldWildPreparedSpawn;
    _Static_assert(sizeof(OverworldWildPreparedSpawn)==260,"packet seam must include every byte");
    typedef struct OverworldWildOverlayRuntimeState {''')
    fixture=fixture.replace('struct {u8 targets[10];u16 targetMask,carrierMask,recoveringMask;} throwState;','struct {u8 targets[10];u16 targetMask,carrierMask,recoveringMask;} throwState;\n    OverworldWildPreparedSpawn queuedSpawn;u32 queuedSpawnSerial;u32 refillQueuedSerial;u8 refillFailureStreak,refillTerrainMask,refillLandSurfSlot;u8 queuedSpawnSlotPlusOne;\n    OverworldEntryRouteReceipt entryRouteReceipt;')
    fixture=fixture.replace('u16 captureTargetMask;','u16 captureTargetMask;u8 justSpawned;u16 movementInProgressMask;int movementQueuedBattleSlot;u8 movementSpotStates[10];u8 movementSpawnRunActive[10];s16 movementSpawnRunTargetX[10],movementSpawnRunTargetY[10];')
    # Motion model supplies the actual enums already.
    fixture=fixture.replace('#include "cargo_motion_decision_production.inc"','')
    fixture=fixture.replace('static const OverworldPickupRouteWildOps ops={','static int WalkHeight(FieldSystem*f,const void*v,int x,int y,u8*t){(void)f;(void)v;(void)x;(void)y;*t=0;return 0;}\nstatic BOOL RawBlocked(FieldSystem*f,int x,int y){(void)f;(void)x;(void)y;return 0;}\nstatic const OverworldPickupRouteWildOps ops={').replace('.walkTerrain=WalkTerrain,','.walkTerrain=WalkTerrain,.walkHeight=WalkHeight,.blockedTerrain=RawBlocked,')
    # Real leaf in same fixture unit; rename only its private Abs to avoid Cargo's extracted Abs collision.
    fixture=fixture.replace('#include "cargo_walk_policy_production.inc"',plain('lib/overworld/overworld_prepared_movement.c').replace('Abs(','PreparedAbs(').replace('Finish(','PreparedFinish(')+'\n#include "cargo_walk_policy_production.inc"')
    # Original Cargo tests must never enter the new Entry branches.
    stubs=r'''
    #define NEVER() do{fprintf(stderr,"unexpected entry control in normal Cargo\n");abort();}while(0)
    /* Exact ResetMemo body is included below from the actual Entry unit. */
    OverworldPickupRouteStatus OverworldEntryRoute_Begin(OverworldEntryRouteSearch*s,const OverworldEntryRouteRequest*r,const OverworldPickupRouteWildWorld*w,const OverworldPickupRouteNativePolicy*p,OverworldCargoQueryState*l,const OverworldPickupRouteEdge*e,u16 n,const OverworldPickupRouteBounds*b,u32 sc,u32 pc,u32 dc,u8(*c)(void*,const OverworldEntryRouteRequest*),void*o){(void)s;(void)r;(void)w;(void)p;(void)l;(void)e;(void)n;(void)b;(void)sc;(void)pc;(void)dc;(void)c;(void)o;NEVER();}
    OverworldPickupRouteStatus OverworldEntryRoute_Resume(OverworldEntryRouteSearch*s,u32 d,const OverworldCargoQueryChangedTile*t,u16 n,u8 c,OverworldEntryRoutePath*p,OverworldEntryRouteReceipt*r){(void)s;(void)d;(void)t;(void)n;(void)c;(void)p;(void)r;NEVER();}
    OverworldPickupRouteStatus OverworldEntryRoute_ValidateStep(OverworldEntryRouteSearch*s,const OverworldEntryRoutePath*p,u32 d,const OverworldCargoQueryChangedTile*t,u16 n,u8 c,OverworldEntryRouteReceipt*r){(void)s;(void)p;(void)d;(void)t;(void)n;(void)c;(void)r;NEVER();}
    /* Exact Confirm is included below. */
    /* Exact IdleStall is included below. */
    const OverworldPickupRouteNativeSeams *OverworldEntryRoute_MemoSeams(void){NEVER();}
    '''
    entry=product(root,'lib/overworld/overworld_entry_route.c')
    a=entry.index('void OverworldEntryRoute_ResetMemo(');b=entry.index('\nstatic u8 Current(',a)
    stubs+=entry[a:b]
    a=entry.index('u8 OverworldEntryRoute_Confirm(');stubs+=entry[a:entry.index('/* Synchronous native glue')]
    fixture=fixture.replace('static FieldSystem field;',stubs+'\nstatic FieldSystem field;',1)
    # Append the actual private ABI only after complete named host types.
    header = product(root,'include/overworld_entry_route.h')
    native_header = header[header.index('/* Native glue'):header.rfind('#endif')]
    fixture = fixture.replace('#include "cargo_query_wild_production.inc"', native_header+'\n#include "cargo_query_wild_production.inc"')
    native_body = without_includes(entry[entry.index('/* Synchronous native glue'):])
    # The actual relocated refill loop uses the same native constants as Wild.
    # Keep these host seam values tied to their current product declarations.
    slots = product(root,'include/overworld_wild_spawns_internal.h')
    slot_names = ('OW_WILD_LAND_SURF_MAX_SPAWNS','OW_WILD_HEADBUTT_MAX_SPAWNS',
                  'OW_WILD_FISH_MAX_SPAWNS','OW_WILD_HEADBUTT_SLOT_START','OW_WILD_FISH_SLOT_START')
    constants = '\n'.join(line for line in slots.splitlines()
                          if line.split()[:2] in [['#define',name] for name in slot_names]) + '\n'
    if constants.count('#define') != len(slot_names):
        raise AssertionError('current native refill slot constants changed')
    overlay = product(root,'src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c')
    for name in ('OW_WILD_REFILL_BASE_INTERVAL_FRAMES','OW_WILD_REFILL_FULL_DENSITY_COUNT','OW_WILD_REFILL_SPARSE_INTERVAL_FRAMES'):
        found = re.findall(r'^#define '+name+r' \d+$',overlay,re.M)
        if len(found) != 1:
            raise AssertionError('current refill density constant changed: '+name)
        constants += found[0]+'\n'
    terrain = type_decl(product(root,'include/overworld_wild_behavior_data.h'),
                        'OverworldWildSpawnTerrain','enum')
    constants += terrain.replace('typedef enum OverworldWildSpawnTerrain','enum').replace('} OverworldWildSpawnTerrain;','};')+'\n'
    helper = product(root,'include/overworld_wild_helper.h')
    a=helper.index('#define OW_WILD_HELPER_SPAWN_POSITION_ATTEMPT_CHECKS ')
    constants += helper[a:helper.index('\ntypedef ',a)]+'\n'
    fixture = fixture.replace('static FieldSystem field;',constants+'static int Abs(int);\n'+native_body+'\nstatic FieldSystem field;',1)
    fixture=re.sub(r'#include "../../../([^"]+)"',lambda m:'#include "'+str(product_path(root,m.group(1)))+'"',fixture)

    fixture=fixture.replace('int main(int argc,char **argv)', 'int CargoMain(int argc,char **argv)')
    fixture=fixture.replace('    OverworldEntryRouteReceipt entryRouteReceipt;', '    OverworldEntryRouteReceipt entryRouteReceipt;u32 entryRouteSerial[10];struct {u8 phase;} returnMoves[10];u8 queuedSpawnTerrain,refillPositionChecksRemaining;OverworldWildQueuedSpawnGuard queuedSpawnGuard;')
    return fixture

def guided_program(root=ROOT, fault=None):
    fixture = cargo_fixture(root)
    entry = product(root,'lib/overworld/overworld_entry_route.c')
    guide = entry[entry.index('u8 OverworldEntryRoute_Guide('):entry.index('u8 OverworldEntryRoute_Confirm(')]
    wild = product(root,'src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c')
    names = ('OverworldWildSpawns_EntryControl','OverworldWildSpawns_ArmEntryQueue',
             'OverworldWildSpawns_QueryEntry','OverworldWildSpawns_FinalizePreparedSpawn',
             'OverworldWildSpawns_TryStartGuidedEntry','OverworldWildSpawns_ApplyRefillDelay','OverworldWildSpawns_CommitQueuedSpawn',
             'OverworldWildSpawns_SpawnOne')
    callers = '\n'.join(wild_function(wild,name) for name in names)
    start = wild_function(wild,'OverworldWildSpawns_StartEntryEdge')
    start = start.replace('profile->jumpLevel','profile->owner.jumpLevel')
    driver = product(root,'tools/overworld/fixtures/spawn_move_guided_driver.c')
    internal = product(root,'include/overworld_actor_system_internal.h')
    operations = type_decl(internal,'OverworldActorPopulationControlOperation','enum')
    # These Entry controls own only direct/manual queues. A natural schedule
    # here is unintended; the refill fixture replaces this named seam with
    # the actual Population reducer and its explicit ordinary-series receipt.
    driver = operations + '\nstatic u8 OverworldWildSpawns_PopulationControl(u8 operation,u16 delay) {(void)operation;(void)delay;NEVER();}\n' + driver
    driver = driver.replace('/* ACTUAL START OWNER */',start)
    driver = driver.replace('/* ACTUAL GUIDE AND CALLER */',guide+callers)
    fixture = fixture.replace('static int Abs(int);','static OverworldPickupRouteStatus ProvedGuide(const OverworldCargoQueryWildCall *,OverworldCargoQueryResult *);\nstatic int Abs(int);',1)
    fixture = mutate(fixture,'return OverworldCargoQueryWild_Tick(&call,&result);','return ProvedGuide(&call,&result);')
    body = product(root,'lib/overworld/overworld_cargo_query_wild.c')
    if fault == 'post-start-sequence':
        # The actual START owner must sample before synchronous Teleport END.
        driver = mutate(driver,'*sequence=actors->slots[slot].snapshot.commitSequence;',
                        '*sequence=actors->slots[slot].snapshot.commitSequence+1;')
    elif fault == 'consume-order':
        fixture = mutate(fixture,'runtime->queuedSpawnSlotPlusOne = 0;\n    runtime->refillPositionChecksRemaining = 0;\n    if ((u32)slot',
                         'runtime->queuedSpawnSlotPlusOne = runtime->queuedSpawnSlotPlusOne;\n    runtime->refillPositionChecksRemaining = 0;\n    if ((u32)slot')
    elif fault == 'guard-tail':
        fixture = mutate(fixture,'byte < sizeof(guard);','byte < sizeof(guard)-4;')
    files = {'check.c':fixture+driver,'cargo_query_wild_production.inc':cargo.host_body(body)}
    header = product(root,'include/overworld_behavior_condition_runtime.h')
    files['cargo_prepared_production.inc'] = type_decl(header,'OverworldBehaviorConditionPreparedActor')
    read = product(root,'lib/overworld/overworld_cargo_read_wild.c')
    files['cargo_read_wild_observe_production.inc'] = read[read.index('u32 OverworldCargoReadWild_Observe('):read.index('\nconst OverworldActorSystemState *')]
    held = product(root,'lib/overworld/overworld_throw_held_wild.c')
    files['cargo_release_production.inc'] = held[held.index('BOOL OverworldThrowHeldWild_ReleaseCargo('):held.index('\n/* The shared held intent')]
    route = product(root,'lib/overworld/overworld_pickup_route_wild.c')
    files['cargo_walk_policy_production.inc'] = pickup.function(route,'Abs','int')+pickup.function(route,'EdgePolicy','Result')
    return files


def entry_root_program(root=ROOT, fault=None):
    """Actual Entry memo/root and Wild occupancy; ordinary Landing unchanged."""
    source=product(root,'lib/overworld/overworld_entry_route.c')
    if fault == 'old-root-mode':
        source=mutate(source,'    if (result==LEGAL) w->routeRead=1;\n','')
    elif fault is not None:
        raise AssertionError('unknown root copied fault: '+fault)
    return {'check.c':pickup.entry_root_source(
        product(root,'lib/overworld/overworld_pickup_route_wild.c'),source)}


def prepared_policy_program(root=ROOT, fault=None):
    """Use the actual Policy body in the existing native-control host fixture."""
    files=guided_program(root)
    files['check.c']=mutate(files['check.c'],
        'int main(void){return NativeControls();}',
        'int main(void){return PreparedPolicyParity();}')
    if fault == 'old-prepared-key':
        files['cargo_query_wild_production.inc']=mutate(
            files['cargo_query_wild_production.inc'],
            '        hash=Hash(hash,0);hash=Hash(hash,0);\n','')
    elif fault is not None:
        raise AssertionError('unknown prepared policy copied fault: '+fault)
    return files



def saved_witness_program(root=ROOT, fault=None):
    """Actual ADOPT/EntryTick/memo/ValidateStep with named stock read seams.

    Use a trusted full prepared path, then prove that an idle Actor's zero
    last-destination token cannot hide the native root support or drop that
    path. No native layout, guest motion, or pacing claim is made here.
    """
    files=guided_program(root)
    unit=cargo_fixture(root)
    start=unit.index('    #define NEVER()')
    end=unit.index('\n#define OW_WILD_LAND_SURF_MAX_SPAWNS ',start)
    core=without_includes(product(root,'lib/overworld/overworld_entry_route.c')).split('/* Synchronous native glue')[0]
    # Separate the Entry unit's private names from the existing Cargo fixture.
    for old,new in (('Same','EntrySame'),('Abs','EntryAbs'),('Current','EntrySearchCurrent'),
                    ('Terrain','EntryTerrain'),('Support','EntrySupport'),('Occupancy','EntryOccupancy'),
                    ('Reservations','EntryReservations'),('EdgePolicy','EntryEdgePolicy'),('Hop','EntryHop')):
        core=re.sub(r'\b'+old+r'\b',new,core)
    internal=product(root,'include/overworld_actor_system_internal.h')
    constants='\n'.join(line for line in internal.splitlines()
                        if line.startswith('#define OVERWORLD_ACTOR_HOP_PLAN_'))+'\n'
    constants+=type_decl(internal,'OverworldActorHopPlanOperation','enum')+'\n'
    unit=unit[:start]+'#define NEVER() do {abort();} while(0)\n'+constants+core+'\n#undef INVALID\n#define INVALID OVERWORLD_PICKUP_ROUTE_INVALID\n'+unit[end:]
    unit=mutate(unit,
        '    ((OverworldPickupRouteWildWorld *)raw)->routeRead=q!=NULL;++nativeCalls;\n    return q->subject.slot==expectedSubjectSlot',
        '    ((OverworldPickupRouteWildWorld *)raw)->routeRead=q!=NULL;++nativeCalls;\n    if(q==NULL)return LEGAL;\n    if(q->extension)return OverworldPickupRoute_QueryCurrent(q)?LEGAL:OVERWORLD_PICKUP_ROUTE_EDGE_INVALID;\n    return q->subject.slot==expectedSubjectSlot')
    unit=mutate(unit,'static int missingX=-1,blockedX=-1;',
        'static int missingX=-1,blockedX=-1;static u16 fixtureSurface=0xFFFF;static s32 fixtureHeight=0x7fffffff;')
    unit=mutate(unit,'(void)raw;(void)x;(void)y;(void)tile;*out=from->baseY;return LEGAL;',
        '(void)raw;(void)x;(void)y;(void)tile;*out=fixtureHeight==0x7fffffff?from->baseY:fixtureHeight;return LEGAL;')
    unit=mutate(unit,'    *out=(OverworldPickupRouteNativeTile){NATIVE_GROUND,(u16)(wantedMask&1),0,0,0};return LEGAL;',
        '    OverworldPickupRouteWildWorld*w=raw;if(w->entryMemo){if(!w->entryMemo->budget)return DEFERRED;w->entryMemo->budget--;w->entryMemo->used++;}\n    *out=(OverworldPickupRouteNativeTile){fixtureSurface,1,0,0,0};return LEGAL;')
    unit=mutate(unit,'    for(int n=0;n<64;n++)if((objects[n].flags&1) && &objects[n]!=spawns.spawns[subject->slot].object',
        '    for(int n=0;n<64;n++)if((objects[n].flags&1) && &objects[n]!=((OverworldPickupRouteWildWorld*)raw)->subjectObject')
    unit=mutate(unit,'static const OverworldPickupRouteNativeSeams seams={Bind,Terrain,Support,Occupancy,Reservations,EdgePolicy,Hop,Reach};',
        'static Result EntryPhysicalPolicy(void*w,const OverworldPickupRouteNativePolicy*p,u8 k,const OverworldPickupRoutePosition*f,const OverworldPickupRouteNativeTile*s,const OverworldPickupRoutePosition*t,const OverworldPickupRouteNativeTile*d){(void)w;(void)p;(void)k;(void)f;(void)s;(void)t;(void)d;return LEGAL;}\nstatic const OverworldPickupRouteNativeSeams seams={Bind,Terrain,Support,Occupancy,Reservations,EntryPhysicalPolicy,Hop,Reach};')
    files['check.c']=unit+product(root,'tools/overworld/fixtures/spawn_move_saved_witness_driver.c')
    source=product(root,'lib/overworld/overworld_cargo_query_wild.c')
    if fault=='last-destination-token':
        start=source.index('    /* Motion policy stores its last destination surface, not standing\n')
        end=source.index('    if (request->operation==OVERWORLD_ENTRY_ROUTE_GUIDE && path->valid\n',start)
        source=source[:start]+source[end:]
    elif fault is not None:
        raise AssertionError('unknown saved witness copied fault: '+fault)
    files['cargo_query_wild_production.inc']=cargo.host_body(source)
    return files


def bare_walk_program(root=ROOT, fault=None):
 """Actual bare Landing/Native/EdgePolicy/Prepared Walk with stock seams."""
 wild=product(root,'lib/overworld/overworld_pickup_route_wild.c')
 s=pickup.entry_root_source(wild,product(root,'lib/overworld/overworld_entry_route.c')).split('static const OverworldPickupRouteNativeSeams rootSeams=',1)[0]
 old='typedef struct OverworldEntryRouteMemo {u8 budget,used,valid,count,cursor,terminal,reserved;u16 physicalPlayerMask;OverworldEntryRouteTerrainCursor terrain;OverworldEntryRouteMemoRead reads[40];const OverworldPickupRouteNativeSeams *native;} OverworldEntryRouteMemo;'
 header=without_includes(product(root,'include/overworld_prepared_movement.h'))
 s=mutate(s,old,header+'\n'+old.replace('const OverworldPickupRouteNativeSeams *native;','const OverworldPickupRouteNativeSeams *native;OverworldPreparedMovementInput movementInput;OverworldPreparedMovementCursor movement;u8 movementStarted;'))
 s=mutate(s,pickup.function(s,'FixtureEdge','Result'),pickup.function(wild,'EdgePolicy','Result'))
 s=mutate(s,'.edgePolicy=FixtureEdge','.edgePolicy=EdgePolicy')
 s=mutate(s,'static BOOL SourceBlock(u8 behavior)', 'static int heightReject,rawBlocked,targetBlock,walkHeightCalls,rawCalls,sourceCalls,targetCalls;\nstatic BOOL SourceBlock(u8 behavior)')
 s=mutate(s,'static const OverworldPickupRouteWildOps ops=',r'''
static int WalkHeightExact(FieldSystem*f,const void*raw,int x,int y,u8*out){const VecFx32*v=raw;(void)f;(void)x;(void)y;walkHeightCalls++;observedFromX=v->x;observedFromY=v->z;observedFromBase=v->y;*out=0;return heightReject;}
static BOOL RawBlockedExact(FieldSystem*f,int x,int y){(void)f;(void)x;(void)y;rawCalls++;return rawBlocked;}
static BOOL TargetBlockExact(u8 b){(void)b;targetCalls++;return targetBlock;}
static const OverworldPickupRouteWildDirectionBlock exactTargetBlocks[4]={TargetBlockExact,TargetBlockExact,TargetBlockExact,TargetBlockExact};
static const OverworldPickupRouteWildOps ops=''')
 s=mutate(s,'return behavior==blockSource;','sourceCalls++;return behavior==blockSource;')
 s=mutate(s,'HopPlan,WalkTerrain,sourceBlocks,targetBlocks,FixturePickupReach};','HopPlan,WalkTerrain,sourceBlocks,exactTargetBlocks,FixturePickupReach,WalkHeightExact,RawBlockedExact};')
 prepared=product(root,'lib/overworld/overworld_prepared_movement.c')
 if fault=='old-bare-pair':
  prepared=mutate(prepared,
   '        || (input->profile==NULL)!=(input->lane==NULL)\n        || (input->kind!=OVERWORLD_PICKUP_ROUTE_NATIVE_WALK && input->profile==NULL)\n        || input->field==NULL || input->ops==NULL',
   '        || input->profile==NULL || input->lane==NULL || input->field==NULL || input->ops==NULL')
 elif fault not in (None,'missing-bare-directions'):
  raise AssertionError('unknown bare Walk fault: '+fault)
 s+=without_includes(prepared)
 # Private helpers of the two extracted production units need separate names.
 marker='typedef OverworldPickupRouteEdgeResult Result;\n#define LEGAL OVERWORLD_PICKUP_ROUTE_EDGE_LEGAL\n#define BLOCKED OVERWORLD_PICKUP_ROUTE_EDGE_BLOCKED\n#define DEFERRED OVERWORLD_PICKUP_ROUTE_EDGE_DEFERRED\n#define INVALID OVERWORLD_PICKUP_ROUTE_EDGE_INVALID\n'
 # There is one duplicate Abs in Prepared; rename only that added unit.
 a=s.rindex(marker);s=s[:a]+re.sub(r'\bAbs\b','PreparedAbs',s[a:])
 landing=product(root,'lib/overworld/overworld_pickup_landing_wild.c')
 if fault=='missing-bare-directions':
  landing=mutate(landing,'            policy.directions=OVERWORLD_PICKUP_ROUTE_NATIVE_CARDINAL\n                | OVERWORLD_PICKUP_ROUTE_NATIVE_DIAGONAL;\n','')
 s+=without_includes(landing)
 s+=product(root,'tools/overworld/fixtures/spawn_move_walk_landing_driver.c')
 return {'check.c':s}

def origin_program(root=ROOT, fault=None):
    source = product(root, 'src/overworld_wild_spawns_overlay/overworld_wild_spawns_overlay.c')
    body = wild_function(source, 'OverworldWildSpawns_SpawnPreparedEncounter')
    entry = product(root,'lib/overworld/overworld_entry_route.c')
    ready = wild_function(entry,'NativeReady')
    if fault == 'stale-ready-origin':
        ready = mutate(ready,'Abs(c->prepared->position.startX-player->xCurr)>=13','Abs(c->prepared->position.startX-player->xCurr)>=12')
    driver = (FIXTURES / 'spawn_move_origin_driver.c').read_text()
    return {'check.c':driver.replace('/* ACTUAL READY OWNER */',ready).replace('/* ACTUAL PREPARED CONSTRUCTOR */',body)}


def compile_program(work, files, root=ROOT, linked=False):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (work / name).write_text(text)
    command = [*shlex.split(os.environ.get('HOST_CC', 'cc')), '-std=c11', '-O2',
               '-Wno-unknown-attributes', '-Wno-misleading-indentation', '-Wno-macro-redefined',
               '-DOVERWORLD_ACTOR_SYSTEM_HOST', '-DOVERWORLD_MOTION_HOST',
               '-I', str(Path(root) / 'include'), '-I', str(ROOT / 'include'), '-I', str(work), str(work / 'check.c')]
    if linked:
        command += [str(product_path(root, 'lib/overworld/' + unit)) for unit in
                    ('overworld_cargo_query.c', 'overworld_pickup_route.c', 'overworld_pickup_route_native.c')]
    command += ['-o', str(work / 'check')]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('Move entry host compile failed:\n' + result.stderr)
    return work / 'check'
