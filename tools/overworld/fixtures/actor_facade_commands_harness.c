/* Public command/actor types and actual function bodies. Private storage is
 * projected here; initialization, lookup, world gate and trace are stubs.
 * Full Tick is imported; this fixture holds its frame steady so command
 * draining does not start unrelated motion/engine work. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "overworld_actor_system.h"
#include "overworld_motion_model.h"
typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define ARRAY_COUNT(a) (sizeof(a) / sizeof((a)[0]))
#define CHECK(c) do { if (!(c)) { fprintf(stderr,"actor command invariant failed: %s:%d: %s\n", caseName, __LINE__, #c); exit(1); } } while (0)
static const char *caseName;
typedef struct { u16 pendingFirstPathAdvance, pendingLastPathAdvance; } OverworldActorPolicyState;
typedef struct { OverworldActorStateSnapshot snapshot; OverworldMotionState motion; OverworldActorPolicyState policy; } OverworldActorRuntimeSlot;
typedef struct {
    u16 fieldEpoch, lastReason;
    u8 queueCount, queueHead, ackWriteIndex;
    u32 lastAcknowledgedSequence;
    u32 frame;
    OverworldActorCommand commands[OVERWORLD_ACTOR_SYSTEM_COMMAND_CAPACITY];
    OverworldActorReply acknowledgements[OVERWORLD_ACTOR_SYSTEM_ACK_CAPACITY];
    OverworldActorRuntimeSlot slots[OVERWORLD_ACTOR_SYSTEM_MAX_ACTORS];
    OverworldActorTraceHeader trace;
} OverworldActorSystemState;
static OverworldActorSystemState gOverworldActorSystemState;
static unsigned terminalCount;
static BOOL busy;
static void ActorSystem_EnsureInitialized(void) {}
static void ActorSystem_Zero(void *p, size_t n) { memset(p, 0, n); }
static BOOL ActorSystem_TransitionIsActive(void) { return busy; }
static OverworldActorStateSnapshot *ActorSystem_FindActor(const OverworldActorHandle *h)
{ return memcmp(h, &gOverworldActorSystemState.slots[0].snapshot.handle, sizeof(*h)) ? NULL : &gOverworldActorSystemState.slots[0].snapshot; }
static void ActorSystem_WriteTerminalTrace(OverworldActorStateSnapshot *a, u16 e, u16 r, u32 x, u32 y)
{ CHECK(e == OVERWORLD_ACTOR_EVENT_MOTION_CANCELED); CHECK(r == 9); CHECK(x == a->motionKind && y == a->commitSequence); terminalCount++; }
static void ActorSystem_WriteTrace(const OverworldActorHandle *h, u16 e, u16 r, u32 a, u32 b)
{ (void)h; (void)e; (void)r; (void)a; (void)b; }
static void OverworldActorSystem_CompatibilityUnbindImpl(const OverworldActorHandle *h, u16 r) { (void)h; (void)r; }
static void ActorSystem_ResetTraceRecords(void) {}
/* @BODIES@ */
static void ActorSystem_RecordPathAdvances(OverworldActorRuntimeSlot *s, const OverworldMotionSample *p)
{ (void)s; (void)p; CHECK(FALSE); }
static int ActorSystem_TryAcknowledgeMotionCommit(OverworldActorRuntimeSlot *s, u16 e, void *p)
{ (void)s; (void)e; (void)p; CHECK(FALSE); return 0; }
/* @TICK@ */
static void Drain(void)
{
    OverworldActorFrame frame;
    memset(&frame,0,sizeof(frame)); frame.version=OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    frame.size=sizeof(frame); frame.frame=gOverworldActorSystemState.frame;
    frame.expectedFieldEpoch=gOverworldActorSystemState.fieldEpoch;
    (void)OverworldActorSystem_TickImpl(&frame);
}
static OverworldActorCommand Reset(const char *name)
{
    OverworldActorCommand c;
    caseName = name; memset(&gOverworldActorSystemState, 0, sizeof(gOverworldActorSystemState));
    terminalCount = 0; busy = FALSE;
    gOverworldActorSystemState.fieldEpoch = 2;
    memset(&c, 0, sizeof(c)); c.version = OVERWORLD_ACTOR_SYSTEM_ABI_VERSION;
    c.size = sizeof(c); c.sequence = 1; c.expectedFieldEpoch = 2;
    return c;
}
int main(void)
{
    OverworldActorReply a, b;
    OverworldActorCommand c = Reset("duplicate");
    CHECK(OverworldActorSystem_ApplyImpl(&c,&a) == OVERWORLD_ACTOR_RESULT_OK);
    CHECK(OverworldActorSystem_ApplyImpl(&c,&b) == OVERWORLD_ACTOR_RESULT_OK);
    CHECK(!memcmp(&a,&b,sizeof(a)) && gOverworldActorSystemState.queueCount == 1);
    Drain(); CHECK(gOverworldActorSystemState.queueCount == 0);
    c = Reset("wrap"); gOverworldActorSystemState.lastAcknowledgedSequence = 0xfffffffe;
    c.sequence = 0xffffffff; CHECK(OverworldActorSystem_ApplyImpl(&c,&a) == OVERWORLD_ACTOR_RESULT_OK); Drain();
    c.sequence = 1; CHECK(OverworldActorSystem_ApplyImpl(&c,&a) == OVERWORLD_ACTOR_RESULT_OK); Drain();
    c = Reset("evicted old sequence");
    for (u32 n=1;n<=OVERWORLD_ACTOR_SYSTEM_ACK_CAPACITY+1;n++) { c.sequence=n; CHECK(OverworldActorSystem_ApplyImpl(&c,&a)==OVERWORLD_ACTOR_RESULT_OK); Drain(); }
    c.sequence=1; CHECK(OverworldActorSystem_ApplyImpl(&c,&a)==OVERWORLD_ACTOR_RESULT_REJECTED);
    CHECK(a.reason==OVERWORLD_ACTOR_REASON_STALE_SEQUENCE && !gOverworldActorSystemState.queueCount);
    c = Reset("queue retry"); gOverworldActorSystemState.queueCount=OVERWORLD_ACTOR_SYSTEM_COMMAND_CAPACITY;
    CHECK(OverworldActorSystem_ApplyImpl(&c,&a)==OVERWORLD_ACTOR_RESULT_RETRY);
    CHECK(a.reason==OVERWORLD_ACTOR_REASON_QUEUE_FULL && !gOverworldActorSystemState.lastAcknowledgedSequence && !gOverworldActorSystemState.ackWriteIndex);
    gOverworldActorSystemState.queueCount=0; CHECK(OverworldActorSystem_ApplyImpl(&c,&a)==OVERWORLD_ACTOR_RESULT_OK);
    c = Reset("world retry"); c.kind=OVERWORLD_ACTOR_COMMAND_CANCEL_MOTION; busy=TRUE;
    CHECK(OverworldActorSystem_ApplyImpl(&c,&a)==OVERWORLD_ACTOR_RESULT_RETRY);
    CHECK(a.reason==OVERWORLD_ACTOR_REASON_RETRY_WORLD_BUSY && !gOverworldActorSystemState.lastAcknowledgedSequence && !gOverworldActorSystemState.ackWriteIndex);
    busy=FALSE; CHECK(OverworldActorSystem_ApplyImpl(&c,&a)==OVERWORLD_ACTOR_RESULT_OK);
    c = Reset("execution epoch"); c.kind=OVERWORLD_ACTOR_COMMAND_CANCEL_MOTION; c.valueA=9;
    OverworldActorRuntimeSlot *live=&gOverworldActorSystemState.slots[0];
    live->motion.phase=OVERWORLD_MOTION_PHASE_MOVING; live->motion.plan.kind=OVERWORLD_ACTOR_MOTION_WALK;
    live->motion.plan.duration=8; live->motion.elapsed=2;
    live->snapshot.active=1; live->snapshot.commitSequence=23;
    live->snapshot.reservationId=5; live->snapshot.inputOwnership=1;
    live->policy.pendingFirstPathAdvance=3;
    live->policy.pendingLastPathAdvance=4;
    Drain(); /* establish the normal same-frame public projection */
    OverworldActorRuntimeSlot originalSlot=*live;
    OverworldActorPolicyState originalPolicy=live->policy;
    CHECK(OverworldActorSystem_ApplyImpl(&c,&a)==OVERWORLD_ACTOR_RESULT_OK);
    gOverworldActorSystemState.fieldEpoch=3; Drain();
    CHECK(gOverworldActorSystemState.lastReason==OVERWORLD_ACTOR_REASON_STALE_FIELD && terminalCount==0);
    CHECK(!memcmp(&originalSlot,live,sizeof(originalSlot)));
    CHECK(!memcmp(&originalPolicy,&live->policy,sizeof(originalPolicy)));
    c = Reset("repeat cancel"); c.kind=OVERWORLD_ACTOR_COMMAND_CANCEL_MOTION; c.valueA=9;
    OverworldActorRuntimeSlot *s=&gOverworldActorSystemState.slots[0];
    s->motion.phase=OVERWORLD_MOTION_PHASE_MOVING; s->snapshot.motionKind=OVERWORLD_ACTOR_MOTION_WALK;
    s->snapshot.commitSequence=17; s->snapshot.reservationId=4; s->snapshot.inputOwnership=1;
    CHECK(OverworldActorSystem_ApplyImpl(&c,&a)==OVERWORLD_ACTOR_RESULT_OK); Drain();
    CHECK(terminalCount==1 && s->snapshot.commitSequence==17 && !s->snapshot.inputOwnership && !s->snapshot.reservationId);
    CHECK(OverworldActorSystem_ApplyImpl(&c,&b)==OVERWORLD_ACTOR_RESULT_OK && !memcmp(&a,&b,sizeof(a))); Drain();
    c.sequence=2; CHECK(OverworldActorSystem_ApplyImpl(&c,&b)==OVERWORLD_ACTOR_RESULT_OK); Drain();
    CHECK(terminalCount==1 && s->snapshot.commitSequence==17 && s->motion.phase==OVERWORLD_MOTION_PHASE_CANCELED);
    puts("PASS seven facade command cases (production C, engine stubs)"); return 0;
}
