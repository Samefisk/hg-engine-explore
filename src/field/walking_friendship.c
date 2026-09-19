#include "../../include/pokemon.h"

/* Native party lock keeps the unchanged walking friendship calculation from
 * decrypting and encrypting the same mon for each data field. This wrapper is
 * called only by the field's periodic walking loop, after normal party checks.
 * It does not defer work, change RNG order, or change friendship rules. */
extern BOOL WalkingFriendship_Acquire(struct PartyPokemon *mon);
extern BOOL WalkingFriendship_Release(struct PartyPokemon *mon, BOOL token);
extern void WalkingFriendship_Apply(struct PartyPokemon *mon, u8 kind, u16 location);
__asm__(".thumb\n"
    ".global WalkingFriendship_Acquire\n.thumb_func\n"
    ".thumb_set WalkingFriendship_Acquire, 0x0206DD40\n"
    ".global WalkingFriendship_Release\n.thumb_func\n"
    ".thumb_set WalkingFriendship_Release, 0x0206DD8C\n"
    ".global WalkingFriendship_Apply\n.thumb_func\n"
    ".thumb_set WalkingFriendship_Apply, 0x0206FE90\n");

void __attribute__((section(".walking_friendship"), noinline, used))
OverworldField_ApplyWalkingFriendship(struct PartyPokemon *mon, u8 kind, u16 location)
{
    BOOL token = WalkingFriendship_Acquire(mon);
    WalkingFriendship_Apply(mon, kind, location);
    WalkingFriendship_Release(mon, token);
}
