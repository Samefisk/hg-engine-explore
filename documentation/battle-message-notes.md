# Battle Message Notes

This note captures the battle-message pitfalls that came up while implementing Rising Star.

## Where battle messages come from

- Text lives in `data/text/197.txt` for battle messages.
- Message IDs are defined in `include/constants/battle_message_constants.h`.
- Script-facing print commands live in `asm/include/battle_commands.inc`.
- Script command implementations live in `src/battle/battle_script_commands.c`.

## Important pitfall: message IDs can be off by one

For this project, battle text constants must match the real line numbering in `data/text/197.txt`.

Rising Star exposed an easy mistake:

- `197.txt` contained:
  - `1626` normal
  - `1627` wild
  - `1628` opposing
- The matching constant had to be `1625`, not `1626`.

If the base constant is wrong by one, the "normal" case will print the wild line, and the wild case will print the opposing line.

Before assuming the runtime battler context is wrong, verify the text index alignment first.

## Important pitfall: avoid auto-direction when you already know the exact line

Battle messages can be affected by message-tag direction flags:

- `TAG_DIR`
- `TAG_NO_DIR`

If you already know which exact text ID you want to print, prefer:

- selecting the correct message ID yourself in C
- using `TAG_NO_DIR`

This avoids the engine re-routing the message to a wild/opposing variant unexpectedly.

For Rising Star, the stable approach was:

- choose normal/wild/opposing in C
- print with `TAG_NICKNAME_ABILITY | TAG_NO_DIR`

## Important pitfall: do not rely on raw battler bit tests for perspective

Do not assume a battler is player/enemy from a raw battler bit macro alone.

Prefer:

- `IsClientEnemy(bsys, client_no)`

This is safer than inferring perspective from battler ID shape.

## Important pitfall: inherited script context can be misleading

Post-hit ability scripts may inherit battler/message context that is not the battler you think it is.

For custom self-buff messages:

- seed message-related vars explicitly when needed
- prefer targeting `BATTLER_CATEGORY_ATTACKER` if the attacker is the real source
- avoid depending on generic side-effect categories unless you have confirmed they resolve correctly in that exact script path

For Rising Star, the subscript explicitly seeds:

- `BSCRIPT_VAR_BATTLER_STAT_CHANGE`
- `BSCRIPT_VAR_MSG_BATTLER_TEMP`

from the attacker before running the boost sequence.

## Recommended workflow for new custom battle messages

1. Add the text to `data/text/197.txt`.
2. Confirm the true line number around the new entry with `nl -ba data/text/197.txt`.
3. Set the constant in `include/constants/battle_message_constants.h` to match the real base index.
4. If the message has separate normal/wild/opposing lines, select the exact line in C instead of relying on automatic direction.
5. Use `TAG_NO_DIR` when printing an already-resolved message ID.
6. Use `IsClientEnemy(bsys, battler)` for player/enemy checks.
7. If the message belongs to a custom post-hit or side-effect flow, seed the battler/message vars explicitly before printing.

## Good debug checklist

If a custom battle message prints the wrong perspective:

1. Check the message constant against `197.txt`.
2. Check whether the print path is using `TAG_DIR` when it should use `TAG_NO_DIR`.
3. Check whether the battler is being resolved with `IsClientEnemy`.
4. Check whether the script is printing from the correct battler category.
5. Check whether inherited `state_client`, `battlerIdTemp`, or `MSG_BATTLER_TEMP` values are stale for that script path.
