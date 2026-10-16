# Three emote slots

Run `scripts/owctl scenario run presentation.emote-three-slots --json` on the current ROM.
This one prepared case binds four fresh Wild Cyndaquil and uses six fixed native quiet calls:
A0,A1,B1,C2,D3,C3. Actual Admit returns must be yes,no,yes,yes,no,no.

The exact148-byte native owner must hold three distinct active effects, models,
texture keys and palette keys. Native104-byte effect data and each borrowed
model bind every frame destination to its own slot. Native update and visible
draw calls on all three occur during240 ordinary completed neutral updates.
PlaySE1501 occurs only in the three accepted initializers. Each quiet request
calls StopSE1501. No screenshot or dry-run capacity result receives credit.

All three native effects retire, then VWait frees each key and source exactly
once with the transfer queue empty. The owner returns to count0, clear slots
and no cleanup task. Model count and native VRAM free totals return to baseline.
The runner must close its private session. Unknown identity or missing evidence fails.
