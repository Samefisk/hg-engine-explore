#include "../../include/types.h"

/* Mark the existing resident division imports as Thumb entries. */
__asm__(
    ".global __aeabi_idiv\n.thumb_func\n.thumb_set __aeabi_idiv, 0x023DEE44\n"
    ".global __aeabi_idivmod\n.thumb_func\n.thumb_set __aeabi_idivmod, 0x023DEE44\n");

/* The shared Hop height interpolation is hosted in unused boot-resident
 * Walk code space. Task6 already borrows this resident page for Teleport. */
static s32 __attribute__((section(".overworld_hop_lerp"), noinline, used, optimize("Os"))) OverworldActorHopPlanner_LerpFx32(
    s32 start,
    s32 target,
    u32 elapsed,
    u32 total)
{
    s32 delta;
    s32 quotient;
    s32 remainder;

    if (elapsed >= total) {
        return target;
    }
    delta = target - start;
    quotient = delta / (s32)total;
    remainder = delta - quotient * (s32)total;
    return start + quotient * (s32)elapsed
        + remainder * (s32)elapsed / (s32)total;
}


/* Export only the private fixed-address symbol for the placement guard. */
__asm__(".global OverworldActorHopPlanner_LerpFx32\n");
