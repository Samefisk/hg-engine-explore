#include <assert.h>
#include <stdio.h>

/* Exercise the same clipping code that the resident overlay compiles. */
#define PLAYER_HEALTH_CONTACT_CLIP_HOST
#include "../../src/player_health_contact.c"

static BOOL Hit(s32 oldX, s32 oldY, s32 oldZ,
    s32 newX, s32 newY, s32 newZ)
{
    PlayerHealthContactSegment segment = {
        oldX, oldY, oldZ, newX, newY, newZ, FALSE
    };
    return PlayerHealthContact_ThrowIntersectsPlayer(&segment);
}

int main(void)
{
    /* X enters after Y leaves. Both times used to round to 10/1024. */
    assert(!Hit(-513, 1279, 0, -414, 1380, 0));
    /* The same two boundaries touched at exactly 1/99 are a real hit. */
    assert(Hit(-513, 1279, 0, -414, 1378, 0));
    assert(Hit(-600, 0, 0, 600, 0, 0));
    assert(!Hit(-600, 0, 0, -513, 0, 0));
    puts("player health contact clip: pass");
    return 0;
}
