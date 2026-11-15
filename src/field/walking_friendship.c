#include "../../include/pokemon.h"

/* Keep the stock walking draw ahead of any data lock. The selected path
 * recreates the stock entry frame and enters its unchanged body after that
 * draw. Normal field party checks precede this caller. No data, item rule,
 * RNG draw or friendship update is deferred or repeated. */
__asm__(".thumb\n"
    ".global WalkingFriendship_Random\n.thumb_func\n"
    ".thumb_set WalkingFriendship_Random, 0x0201FD44\n"
    ".global WalkingFriendship_Acquire\n.thumb_func\n"
    ".thumb_set WalkingFriendship_Acquire, 0x0206DD40\n"
    ".global WalkingFriendship_Release\n.thumb_func\n"
    ".thumb_set WalkingFriendship_Release, 0x0206DD8C\n");

void __attribute__((section(".walking_friendship"), naked, noinline, used))
OverworldField_ApplyWalkingFriendship(struct PartyPokemon *mon __attribute__((unused)),
    u8 kind __attribute__((unused)), u16 location __attribute__((unused)))
{
    __asm__ volatile(
        ".syntax unified\n"
        "push {r3-r7, lr}\n"
        "movs r4, r0\n"
        "movs r5, r1\n"
        "movs r6, r2\n"
        "cmp r5, #5\n"
        "bne 1f\n"
        "bl WalkingFriendship_Random\n"
        "lsls r0, r0, #31\n"
        "bne 2f\n"
        "1:\n"
        "movs r0, r4\n"
        "bl WalkingFriendship_Acquire\n"
        "movs r7, r0\n"
        "movs r0, r4\n"
        "movs r1, r5\n"
        "movs r2, r6\n"
        "bl 3f\n"
        "movs r0, r4\n"
        "movs r1, r7\n"
        "bl WalkingFriendship_Release\n"
        "2:\n"
        "pop {r3-r7, pc}\n"
        "3:\n"
        "push {r3-r7, lr}\n"
        "sub sp, #8\n"
        "movs r6, r1\n"
        "movs r5, r0\n"
        "str r2, [sp, #0]\n"
        "ldr r3, 4f\n"
        "bx r3\n"
        ".balign 4\n"
        "4: .word 0x0206FEA9\n"
        ".syntax divided\n");
}
