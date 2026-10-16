"""Execute the actual foot-knockback cleanup at the stock boundary.

The native running-hit baseline proves the rendered run selector remains
after unkA0 is idle. Stock stand-ins check the real cleanup's order and owners.
"""
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest

from scripts.verify_overworld_mount import function_body

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(os.environ.get("PLAYER_HEALTH_KNOCKBACK_SOURCE",
                             ROOT / "src/player_health.c"))

STUBS = r'''
#include <stdio.h>
#include <stdlib.h>
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned u32;
typedef int BOOL;
typedef struct { int x, y, z; } VecFx32;
#define TRUE 1
#define FALSE 0
#define OVERWORLD_FIELD_TERRAIN_STREAM_REBIND 2
#define OVERWORLD_FIELD_TERRAIN_STREAM_CANCEL 3
#define OVERWORLD_MOTION_PHASE_IDLE 0
#define OVERWORLD_MOTION_PHASE_CANCELED 5
#define PLAYER_HEALTH_KNOCKBACK_FORCED_FLAG 1u
typedef struct LocalMapObject {
    u32 flags, posVec[3], faceVec[3], unk88[3];
    int xCurr, yCurr, xPrev, yPrev, curFacing, unkA0, command, step, rendered;
    void (*unkC8)(struct LocalMapObject *);
} LocalMapObject;
typedef struct { LocalMapObject *mapObject; u32 unk0; int move, playerMove; } FIELD_PLAYER_AVATAR;
typedef struct { FIELD_PLAYER_AVATAR *playerAvatar; } FieldSystem;
typedef struct { int phase; struct { int startBaseY; } plan; } Motion;
static struct {
    int streamActive, fieldContext, active, mounted, baseFaceY, baseUnk88Y;
    FieldSystem *fieldSystem; LocalMapObject *playerObject;
    Motion motion; int pending, waitFrames;
} sKnockback;
static LocalMapObject player, otherPlayer;
static FIELD_PLAYER_AVATAR avatar = {&player, 1, 2, 2};
static FieldSystem field = {&avatar}, otherField;
static FieldSystem *gFieldSysPtr = &field;
static int streamRebind, streamCancel, positionCalls, heightCalls, clearCalls, resetCalls, spriteCalls, motionCancel;
static int CurrentContext(void) { return 7; }
static struct { int (*getContext)(void); } entry = {CurrentContext};
#define OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY (&entry)
static BOOL PlayerHealthKnockback_Stream(int op) {
    if (op == OVERWORLD_FIELD_TERRAIN_STREAM_REBIND) streamRebind++;
    else if (op == OVERWORLD_FIELD_TERRAIN_STREAM_CANCEL) streamCancel++;
    else abort(); return TRUE;
}
/* Vanilla SetPosition clears held movement but leaves the animation selector. */
static void MapObject_SetPositionFromVectorAndDirection(LocalMapObject *p, VecFx32 *v, int dir) {
    if (p != &player || v != (VecFx32 *)p->posVec || dir != p->curFacing) abort();
    positionCalls++; p->xPrev = p->xCurr; p->yPrev = p->yCurr;
}
static BOOL MapObject_RefreshHeightFromTerrain(LocalMapObject *p) {
    if (p != &player) abort(); heightCalls++; return TRUE;
}
/* Stock 020621F0 writes flags, command and step. It does not write unkA0. */
static void PlayerHealth_ClearObjectCommand(LocalMapObject *p) {
    if (p != &player) abort(); clearCalls++;
    p->flags = (p->flags & ~0x10u) | 0x20u; p->command = 255; p->step = 0;
}
/* Stock 0205CF44 resets avatar states. It does not write the map object. */
static void PlayerAvatar_ResetMovement(FIELD_PLAYER_AVATAR *p) {
    if (p != &avatar) abort(); resetCalls++; p->move = p->playerMove = 0;
}
/* Stock 0205F484 invokes the object's registered presentation callback. */
static void PlayerHealth_RefreshObjectSprite(LocalMapObject *p) {
    if (p != &player || p->unkA0 != 0 || p->command != 255 || p->step != 0
        || avatar.unk0 & 1 || avatar.move || avatar.playerMove
        || resetCalls != 1 || clearCalls != 1 || heightCalls != 1) abort();
    spriteCalls++; p->rendered = p->unkA0;
}
static BOOL OverworldActorSystem_IsReady(void) { return TRUE; }
static void OverworldMotion_Cancel(Motion *motion, u8 reason) {
    if (motion != &sKnockback.motion || reason != 1) abort();
    motionCancel++; motion->phase = OVERWORLD_MOTION_PHASE_CANCELED;
}
'''

CASES = r'''
#define CHECK(v) do { if (!(v)) { fprintf(stderr, "%d: %s\n", __LINE__, #v); return 1; } } while (0)
int main(int argc, char **argv) {
    CHECK(argc == 2); int mode = atoi(argv[1]);
    player.flags = 0x11; player.xCurr = 585; player.yCurr = 407;
    player.xPrev = 585; player.yPrev = 406; player.curFacing = 1;
    player.command = 62; player.step = 1; player.unkA0 = 2; player.rendered = 2;
    player.unkC8 = PlayerHealth_RefreshObjectSprite;
    player.faceVec[1] = 999; player.unk88[1] = 888;
    sKnockback.active = 1; sKnockback.pending = 1; sKnockback.waitFrames = 10;
    sKnockback.fieldSystem = &field; sKnockback.playerObject = &player;
    sKnockback.motion.phase = 3; sKnockback.motion.plan.startBaseY = 65536;
    sKnockback.baseFaceY = 0; sKnockback.baseUnk88Y = 0;
    sKnockback.streamActive = 1; sKnockback.fieldContext = 6;
    if (mode == 1) sKnockback.mounted = 1;
    if (mode == 2) sKnockback.fieldSystem = &otherField;
    if (mode == 3) avatar.mapObject = &otherPlayer;
    if (mode == 4) sKnockback.active = 0;
    if (mode == 5) player.unkA0 = 0;
    if (mode == 6) player.unkA0 = 9;
    PlayerHealthKnockback_Cancel();
    CHECK(!sKnockback.active && !sKnockback.pending && !sKnockback.streamActive
          && sKnockback.fieldSystem == NULL && sKnockback.playerObject == NULL
          && sKnockback.waitFrames == 0 && motionCancel == 1);
    CHECK(streamCancel == (mode != 2) && streamRebind == (mode != 2));
    if (mode == 0 || mode == 5 || mode == 6) {
        CHECK(player.unkA0 == 0 && player.rendered == 0 && spriteCalls == 1);
        CHECK(positionCalls == 1 && heightCalls == 1 && clearCalls == 1 && resetCalls == 1);
        CHECK(player.posVec[0] == (585u << 16) + 0x8000
              && player.posVec[2] == (407u << 16) + 0x8000
              && player.posVec[1] == 65536 && player.faceVec[1] == 0 && player.unk88[1] == 0);
        CHECK(player.command == 255 && player.step == 0 && !(player.flags & 0x10)
              && player.flags & 0x20 && !(avatar.unk0 & 1)
              && avatar.move == 0 && avatar.playerMove == 0);
    } else {
        CHECK(player.unkA0 == 2 && player.rendered == 2 && spriteCalls == 0
              && positionCalls == 0 && heightCalls == 0
              && clearCalls == 0 && resetCalls == 0 && player.command == 62
              && player.step == 1 && avatar.unk0 == 1);
    }
    return 0;
}
'''


class PlayerKnockbackAnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        source = Path(cls.tmp.name) / "cancel.c"
        source.write_text(STUBS + "\nstatic void PlayerHealthKnockback_Cancel(void)\n{\n"
                          + function_body(SOURCE.read_text(), "PlayerHealthKnockback_Cancel")
                          + "\n}\n" + CASES)
        cls.binary = Path(cls.tmp.name) / "cancel"
        subprocess.run([*shlex.split(os.environ.get("CC", "cc")), "-std=c99", "-O2",
                        str(source), "-o", str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_real_cleanup_and_existing_owner_exclusions(self):
        for name, mode in (("stale-run-selector", 0), ("mounted-owner", 1),
                           ("wrong-field", 2), ("wrong-player-object", 3),
                           ("pending-without-active", 4), ("already-idle", 5), ("run-selector", 6)):
            with self.subTest(name=name):
                subprocess.run([str(self.binary), str(mode)], check=True,
                               capture_output=True, text=True)


START_STUBS = r'''
#include <stdio.h>
#include <stdlib.h>
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned u32;
typedef int s32;
typedef int BOOL;
typedef struct { int x, y, z; } VecFx32;
#define TRUE 1
#define FALSE 0
#define PLAYER_HEALTH_KNOCKBACK_WAIT_LIMIT 90
#define PLAYER_HEALTH_KNOCKBACK_FORCED_FLAG 1u
#define PLAYER_HEALTH_KNOCKBACK_FREEZE_COMMAND 62
#define OVERWORLD_FIELD_TERRAIN_STREAM_QUERY_IDLE 0
#define OVERWORLD_FIELD_TERRAIN_STREAM_BEGIN 1
#define OVERWORLD_FIELD_TERRAIN_STREAM_IDLE 0
#define OVERWORLD_FIELD_TERRAIN_STREAM_WAITING 1
#define OVERWORLD_MOTION_PATH_ADVANCE_PLAYER 2
#define OVERWORLD_MOTION_DECISION_ACCEPTED 0
#define OVERWORLD_MOUNT_ACTION_ADAPTER_VERSION 1
#define OVERWORLD_MOUNT_ACTION_START_KNOCKBACK 1
#define OVERWORLD_MOUNT_ACTION_STARTED 1
#define OVERWORLD_MOUNT_ACTION_FINAL 2
typedef struct { u32 posVec[3], faceVec[3], unk88[3]; int xCurr, yCurr, curFacing; } LocalMapObject;
typedef struct { LocalMapObject *mapObject; u32 unk0; } FIELD_PLAYER_AVATAR;
typedef struct { unsigned mapId; } Location;
typedef struct { FIELD_PLAYER_AVATAR *playerAvatar; Location *location; } FieldSystem;
typedef struct { int startX, startY; u8 direction, pathAdvancePolicy; } OverworldMotionPlan;
typedef struct { OverworldMotionPlan plan; } OverworldMotionState;
typedef struct { int unused; } OverworldMountRuntimeState;
typedef struct { u16 version,size; u8 operation; OverworldMountRuntimeState *state; FIELD_PLAYER_AVATAR *avatar; u32 *trajectory; } OverworldMountActionCall;
static struct { FieldSystem *fieldSystem; LocalMapObject *playerObject; OverworldMotionState motion;
    u32 fieldContext; unsigned mapId,motionIdentity; u8 type,distance,direction,mounted,pending,active,streamActive,waitFrames;
    int baseFaceY,baseUnk88Y; } sKnockback;
static LocalMapObject player;
static FIELD_PLAYER_AVATAR avatar={&player,0};
static Location location={33};
static FieldSystem field={&avatar,&location}, *gFieldSysPtr=&field;
static OverworldMountRuntimeState mount;
#define OVERWORLD_MOUNT_RUNTIME_STATE_ADDR (&mount)
static unsigned context(void){return 7;}
static struct {unsigned (*getContext)(void);} entry={context};
#define OVERWORLD_ACTOR_SYSTEM_COMPAT_ENTRY (&entry)
static int singleMoving,mountMoving,plans,begins,idleQueries,streamBegins,mountStarts,resets,positions,commands,cancels;
static u32 streamX,streamZ;
static int MapObject_IsSingleMovementActive(LocalMapObject *p){if(p!=&player)abort();return singleMoving;}
static BOOL PlayerHealthField_MountMoving(FieldSystem *f){if(f!=&field)abort();return mountMoving;}
static BOOL PlayerHealthField_IsMounted(FieldSystem *f){if(f!=&field)abort();return sKnockback.mounted;}
static BOOL PlayerHealthField_IsEligible(FieldSystem *f){return f==&field;}
static BOOL OverworldCombat_MountedCrashPending(FieldSystem *f){(void)f;return FALSE;}
static BOOL OverworldCombat_Plan(FieldSystem *f,LocalMapObject *p,u8 options,u8 direction,OverworldMotionPlan *plan){
    if(f!=&field||p!=&player||options!=14||direction!=1)abort();plans++;
    *plan=(OverworldMotionPlan){p->xCurr,p->yCurr,direction,1};return TRUE;
}
static void PlayerHealthKnockback_Cancel(void){cancels++;sKnockback.pending=sKnockback.active=0;}
static int OverworldMotion_Begin(OverworldMotionState *m,const OverworldMotionPlan *plan){
    if(m!=&sKnockback.motion||plan->pathAdvancePolicy!=2)abort();begins++;m->plan=*plan;return 0;
}
static int PlayerHealthKnockback_Stream(int op){
    if(op==OVERWORLD_FIELD_TERRAIN_STREAM_QUERY_IDLE){idleQueries++;return 0;}
    if(op!=OVERWORLD_FIELD_TERRAIN_STREAM_BEGIN||begins!=1||resets||positions||commands||avatar.unk0)abort();
    streamBegins++;streamX=player.posVec[0];streamZ=player.posVec[2];return 1;
}
static int mountDispatch(OverworldMountActionCall *call){
    if(call->version!=1||call->size!=sizeof(*call)||call->operation!=1||call->state!=&mount||call->avatar!=&avatar||!call->trajectory)abort();
    mountStarts++;return 1;
}
#define OVERWORLD_MOUNT_ACTION_ADAPTER_DISPATCH(call) mountDispatch(call)
static void PlayerAvatar_ResetMovement(FIELD_PLAYER_AVATAR *a){if(a!=&avatar||streamBegins!=1)abort();resets++;}
static void MapObject_SetPositionFromVectorAndDirection(LocalMapObject *p,VecFx32 *v,int facing){
    if(p!=&player||v!=(VecFx32*)player.posVec||facing!=player.curFacing||resets!=1)abort();positions++;
}
static void MapObject_StartMovementCommandInternal(LocalMapObject *p,int command){
    if(p!=&player||command!=62||positions!=1||!(avatar.unk0&1))abort();commands++;
}
'''

START_CASES = r'''
#define CHECK(v) do {if(!(v)){fprintf(stderr,"%d: %s\n",__LINE__,#v);return 1;}}while(0)
int main(int argc,char **argv){
    CHECK(argc==2);int mode=atoi(argv[1]);s32 direction=1;u32 newKeys=2,heldKeys=64;
    player.xCurr=585;player.yCurr=407;player.curFacing=1;
    player.posVec[0]=(585u<<16)+0x8000;player.posVec[2]=(407u<<16)+0x8000;
    sKnockback.fieldSystem=&field;sKnockback.mapId=33;sKnockback.pending=1;
    sKnockback.type=2;sKnockback.distance=3;sKnockback.direction=1;
    if(mode==0)player.posVec[0]-=0x4000;
    if(mode==1)player.posVec[2]-=0x2000;
    if(mode==2)player.posVec[0]-=0x10000; /* Center of prior tile, not current tile. */
    if(mode==4){sKnockback.mounted=1;player.posVec[0]-=0x4000;}
    if(mode==5)singleMoving=1;
    if(mode==6){sKnockback.mounted=1;mountMoving=1;}
    u32 oldX=player.posVec[0],oldZ=player.posVec[2];
    u8 result=PlayerHealthKnockback_Control(&avatar,&direction,&newKeys,&heldKeys);
    if(mode==0||mode==1||mode==2||mode==5){
        CHECK(!result&&direction==1&&newKeys==2&&heldKeys==64);
        CHECK(sKnockback.pending&&!sKnockback.active&&!sKnockback.streamActive&&sKnockback.waitFrames==1);
        CHECK(!plans&&!begins&&!idleQueries&&!streamBegins&&!mountStarts&&!resets&&!positions&&!commands&&!cancels);
        CHECK(player.posVec[0]==oldX&&player.posVec[2]==oldZ&&!avatar.unk0);
        /* The stock step finishes itself; the queued hit starts at that boundary. */
        player.posVec[0]=(585u<<16)+0x8000;player.posVec[2]=(407u<<16)+0x8000;singleMoving=0;
        result=PlayerHealthKnockback_Control(&avatar,&direction,&newKeys,&heldKeys);
    }
    if(mode==6){
        CHECK(result&&direction==-1&&!newKeys&&!heldKeys&&sKnockback.pending&&!sKnockback.active);
        CHECK(!plans&&!begins&&!streamBegins&&!mountStarts&&!avatar.unk0);return 0;
    }
    CHECK(result&&direction==-1&&!newKeys&&!heldKeys);
    CHECK(!sKnockback.pending&&sKnockback.active&&sKnockback.playerObject==&player&&plans==1&&!cancels);
    if(mode==4){CHECK(mountStarts==1&&!begins&&!idleQueries&&!streamBegins&&!resets&&!positions&&!commands&&!avatar.unk0);}
    else{
        CHECK(!mountStarts&&begins==1&&idleQueries==1&&streamBegins==1&&resets==1&&positions==1&&commands==1);
        CHECK(sKnockback.streamActive&&sKnockback.waitFrames==0&&(avatar.unk0&1));
        CHECK(streamX==(585u<<16)+0x8000&&streamZ==(407u<<16)+0x8000);
        CHECK(sKnockback.motion.plan.startX==585&&sKnockback.motion.plan.startY==407);
    }
    return 0;
}
'''


class PlayerKnockbackStartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        source = Path(cls.tmp.name) / "start.c"
        actual = SOURCE.read_text()
        center = ""
        if "PlayerHealthKnockback_IsAtGroundCenter" in actual:
            center = ("\nstatic BOOL PlayerHealthKnockback_IsAtGroundCenter(const LocalMapObject *player)\n{\n"
                      + function_body(actual, "PlayerHealthKnockback_IsAtGroundCenter") + "\n}\n")
        source.write_text(START_STUBS
            + center
            + "\nstatic u8 PlayerHealthKnockback_TryStart(FIELD_PLAYER_AVATAR *avatar)\n{\n"
            + function_body(actual, "PlayerHealthKnockback_TryStart") + "\n}\n"
            + "\nstatic u8 PlayerHealthKnockback_Control(FIELD_PLAYER_AVATAR *avatar,s32 *direction,u32 *newKeys,u32 *heldKeys)\n{\n"
            + function_body(actual, "PlayerHealthKnockback_Control") + "\n}\n" + START_CASES)
        cls.binary = Path(cls.tmp.name) / "start"
        subprocess.run([*shlex.split(os.environ.get("CC", "cc")), "-std=c99", "-O2",
                        str(source), "-o", str(cls.binary)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_pending_step_finishes_before_shared_start_and_mounted_path_stays(self):
        for name, mode in (("partial-x", 0), ("partial-z", 1), ("prior-tile-center", 2),
                           ("settled", 3), ("mounted-partial", 4), ("single-move", 5),
                           ("mounted-wait", 6)):
            with self.subTest(name=name):
                subprocess.run([str(self.binary), str(mode)], check=True,
                               capture_output=True, text=True)


if __name__ == "__main__":
    unittest.main()
