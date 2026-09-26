#include "../../include/overworld_mount_internal.h"
#include "../../include/map_events_internal.h"
#include "../../include/overworld_walk_module.h"

/* Keep the resident Thumb division call in Thumb mode. A linker-generated
 * ARM veneer here aborts on the first accelerated mounted Walk. */
__asm__(
    ".thumb\n"
    ".thumb_func\n.thumb_set __aeabi_uidiv, 0x023DEE4C\n");

__asm__(
    ".thumb\n"
    ".thumb_func\n.thumb_set OverworldField_ApplyGraphicsPose, 0x021FA3E9\n");
extern void LONG_CALL OverworldField_ApplyGraphicsPose(
    LocalMapObject *object, void *graphics);

/* The player owns the world motion. Only its rendered position is eased;
 * the tile reservation, elapsed frames, step event, and endpoint do not move. */
void __attribute__((noinline, used, optimize("Os"),
    section(".overworld_mount_walk_ease")))
OverworldWalk_EaseMountedWalk(
    OverworldMountRuntimeState *mount,
    LocalMapObject *player)
{
    u32 phase;
    u32 remaining;
    u32 tangent;
    u32 slope;
    s32 correction;
    s32 progress;

    if (mount->snapshot.motionMode != OVERWORLD_MOUNT_MOTION_WALK
        || mount->motionFlicker == 0
        || mount->motionElapsed >= mount->motionFrameCount
        || mount->motionFrameCount == 0) {
        return;
    }
    phase = (u32)mount->motionElapsed * 256 / mount->motionFrameCount;
    remaining = 256 - phase;
    tangent = phase * remaining / 256;
    tangent = tangent * remaining / 256;
    slope = (u32)mount->motionFrameCount * 256 / mount->motionFlicker;
    if (slope > 768) {
        slope = 768;
    }
    correction = ((s32)slope - 256) * (s32)tangent;
    correction = correction < 0
        ? -(-correction / 256) : correction / 256;
    progress = phase + correction;
    player->posVec[0] = (u32)(
        (s32)mount->motionStartX * 65536 + 32768
        + (s32)(mount->motionTargetX - mount->motionStartX)
            * progress * 256);
    player->posVec[2] = (u32)(
        (s32)mount->motionStartY * 65536 + 32768
        + (s32)(mount->motionTargetY - mount->motionStartY)
            * progress * 256);
}

static void * __attribute__((section(".overworld_mount_graphics_refresh_helper")))
OverworldWalk_MountedGraphics(LocalMapObject *object)
{
    const u32 *state = (const u32 *)object->unk108;
    u32 callback = (u32)object->unkC8;
    u32 graphics;

    /* Match the stock graphics callbacks and their state layouts. Unknown
     * callbacks must keep their own graphics task's pose handling. */
    if (object->flags & MAPOBJECTFLAG_UNK22) {
        return NULL;
    }
    if (callback == 0x021F7895) {
        graphics = state[0];
    } else if (callback == 0x021F88F1) {
        graphics = state[1];
    } else {
        return NULL;
    }
    return (graphics & 0xFFC00000) == 0x02000000
        ? (void *)graphics : NULL;
}

/* The stock shadow is a separate effect. Its task copied the old MapObject
 * position before mounted presentation ran. Touch only the current mount's
 * live shadow position; the stock task still owns visibility and lifetime. */
static void __attribute__((noinline,
    section(".overworld_mount_graphics_refresh_helper")))
OverworldWalk_RefreshMountedShadow(LocalMapObject *mount)
{
    MapObjectMan *objectManager;
    u8 *resource;
    u8 *manager;
    u8 *pool;
    u32 count;
    u32 index;

    /* The field belongs to the MapObject manager. MapObject+0x128 is a
     * stock u16, despite the old local struct label at that offset. */
    objectManager = (MapObjectMan *)mount->unkB4;
    if (objectManager == NULL || objectManager->fsys == NULL) {
        return;
    }
    resource = *(u8 **)((u8 *)objectManager->fsys + 0x44);
    if (resource == NULL) {
        return;
    }
    manager = *(u8 **)(resource + 0x1C);
    if (manager == NULL) {
        return;
    }
    count = *(u32 *)manager;
    pool = *(u8 **)(manager + 0xC);
    if (count > 128 || pool == NULL) {
        return;
    }
    for (index = 0; index < count; index++) {
        u8 *slot = pool + index * 0xC8;
        u32 callback = *(u32 *)(slot + 0xB4);

        if ((*(u32 *)slot & 1) == 0
            || (callback != 0x021FD719 && callback != 0x021FD92D)
            || *(LocalMapObject **)(slot + 0x4C) != mount) {
            continue;
        }
        *(u32 *)(slot + 0x24) = mount->posVec[0];
        *(u32 *)(slot + 0x28) = mount->posVec[1];
        *(u32 *)(slot + 0x2C) = mount->posVec[2];
        break;
    }
}

/* The normal graphics task runs before the mounted motion task. Publish its
 * current pose now so the next camera draw does not see a stale sprite. */
void __attribute__((noinline, used, optimize("Os"),
    section(".overworld_mount_graphics_refresh")))
OverworldWalk_RefreshMountedGraphics(
    LocalMapObject *player, LocalMapObject *mount)
{
    void *graphics = OverworldWalk_MountedGraphics(player);

    if (graphics != NULL) {
        OverworldField_ApplyGraphicsPose(player, graphics);
    }
    graphics = OverworldWalk_MountedGraphics(mount);
    if (graphics != NULL) {
        OverworldField_ApplyGraphicsPose(mount, graphics);
    }
    OverworldWalk_RefreshMountedShadow(mount);
}
