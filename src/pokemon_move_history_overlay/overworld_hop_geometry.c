#include "../pokemon_move_history_task6_overlay/overworld_actor_hop_geometry.h"

void __attribute__((section(".overworld_hop_next_cell"), noinline, used,
    optimize("Os")))
OverworldActorHopGeometry_NextCell(OverworldActorHopGeometry *geometry)
{
    s32 crossedError = geometry->error;

    if (crossedError <= 0) {
        geometry->entryNumerator = geometry->xBoundary;
        geometry->entryDenominator = 2 * geometry->absDx;
        geometry->tileX += geometry->stepX;
        geometry->xBoundary += 2;
        geometry->error += 2 * geometry->absDy;
    }
    if (crossedError >= 0) {
        if (crossedError > 0) {
            geometry->entryNumerator = geometry->yBoundary;
            geometry->entryDenominator = 2 * geometry->absDy;
        }
        geometry->tileY += geometry->stepY;
        geometry->yBoundary += 2;
        geometry->error -= 2 * geometry->absDx;
    }
}
